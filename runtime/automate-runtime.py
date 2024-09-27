import os
import subprocess
import sys
import json
import select
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime

#Run a shell command (enabled logging facility as well)

def run_command(command, cwd=None):
    result = subprocess.Popen(command, shell=True, cwd=cwd,stdout=subprocess.PIPE, stderr=subprocess.PIPE,text=True)
    poll = select.poll()
    poll.register(result.stdout, select.POLLIN)
    poll.register(result.stderr, select.POLLIN)
    
    while True:
        if result.poll() is not None:
            break

        events = poll.poll(1)
        for fd, event in events:
            if fd == result.stdout.fileno():
                output = result.stdout.readline()
                if output:
                    print(output.strip())
                    sys.stdout.flush()
            elif fd == result.stderr.fileno():
                error = result.stderr.readline()
                if error:
                    print(error.strip(), file=sys.stderr)
                    sys.stderr.flush()



    if result.returncode != 0:
        print(f"Error: Command '{command}' failed with exit code {result.returncode}.")
        #sys.exit(result.returncode)
        return result.returncode
    return result.returncode

#installation of dependencies, not used as in general (only for references)

def install_dependencies():
    print("Installing dependencies...")
    dependencies = [
        "sudo apt-get update",
        "sudo apt-get install -y git clang cmake ninja-build libicu-dev libssl-dev libcurl4-openssl-dev zlib1g-dev"
    ]
    for dep in dependencies:
        run_command(dep)

#clone the runtime repository

def clone_repository(repo_url, branch="main"):
    target_dir="runtime"
    if not os.path.exists(target_dir):
        print(f"xxxxx------Cloning repository from {repo_url} with branch {branch}------xxxxxx")
        run_command(f"git clone --branch {branch} {repo_url}")
    else:
        print(f"Repository already exists at {target_dir}. Skipping clone step.")

def get_latest_release_tag(repo):
    # Get the latest release tag using gh command
    result = subprocess.run(
        ["gh", "release", "list", "--repo", repo, "--limit", "1", "--json", "tagName", "--jq", ".[0].tagName"],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        raise Exception(f"Error getting latest release tag: {result.stderr}")
    return result.stdout.strip()


#extracts the dotnet version from the global.json

def get_dotnet_version(repo_dir):

    global_json_path = os.path.join(repo_dir, "global.json")
    
    if not os.path.exists(global_json_path):
        print(f"Error: global.json not found in {repo_dir}")
        return None
    
    with open(global_json_path, 'r') as file:
        data = json.load(file)
    
    try:
        version = data['sdk']['version']
        print(f".NET SDK version in global.json: {version}")
        return version
    except KeyError:
        print("Error: Version information not found in global.json")
        return None

#Attempts to download sdk's from IBM/dotnet-s390x/releases else picks the manual built sdk from saitama951/dotnet-custom-sdk
#NIT: we need a concrete solution for this.
#NIT: git-lfs and gh needs to be installed from source for ***RHEL***

def download_extract_sdk():
    latest_tag = get_latest_release_tag("IBM/dotnet-s390x")

    run_command("mkdir .dotnet/", cwd="runtime")

    print("xxxxx-----downloading the dotnet-sdk version %s-----xxxxx" %(latest_tag))
    success1 = run_command("gh release download %s --repo IBM/dotnet-s390x --pattern \"dotnet-sdk-*-s390x.tar.gz\"" %(latest_tag),cwd="runtime")
    #run_command("git clone https://github.com/saitama951/dotnet-custom-sdk.git")
    #success2 = os.path.exists("./dotnet-custom-sdk/%s/" %(global_version))
    success2 = False
    if success1 != 0 and success2 !=True:
        print("This sdk version is not present in the IBM/dotnet-s390x/releases please build it manually!")
        sys.exit()
    run_command("mkdir packages", cwd="runtime")
    if success1 == 0:
        print("xxxxx-----downloading corresponding arch nupkgs-----xxxxx")
        run_command("gh release download %s --repo IBM/dotnet-s390x --pattern \"*linux-s390x*.nupkg\"" %(latest_tag),cwd="runtime/packages")
        run_command("tar -xf dotnet-sdk-*-linux-s390x.tar.gz --directory .dotnet/", cwd="runtime")

#we don't use this logic, might be useful in the future
    elif success2 == True:
        print("xxxxx------Copying the nupkgs and extracting the sdk from custom-built sdk------xxxxx")
        run_command("cp ../dotnet-custom-sdk/%s/*.nupkg packages/" %(global_version), cwd="runtime")
        run_command("git-lfs install", cwd="dotnet-custom-sdk")
        run_command("git-lfs pull", cwd="dotnet-custom-sdk") #need to build git-lfs from source
        run_command("tar -xf ../dotnet-custom-sdk/%s/dotnet-sdk-*.tar.gz --directory .dotnet/" %(global_version), cwd="runtime")
    
    print("xxxxx-----Adding Nuget Source-----xxxxx")
    run_command(".dotnet/dotnet nuget add source ./packages", cwd="runtime")

    #update global.json
    latest_tag = latest_tag[1:]

    run_command("echo $(jq '.sdk.version = \"%s\" | .tools.dotnet = \"%s\"' global.json)  > global.json" %(latest_tag, latest_tag), cwd="runtime")

    return latest_tag


#build and test the mono runtime
#added a custom path to llvm due to a bug in llvm-17.0.6

def build_and_test_mono_runtime(repo_dir):
    print("xxxxx-----Building and testing Mono runtime for s390x-----xxxxx")
    run_command("./build.sh --cmakeargs -DCMAKE_CXX_COMPILER=\"/home/sanjam/llvm-project/build/bin/clang++\" --cmakeargs -DCMAKE_C_COMPILER=\"/home/sanjam/llvm-project/build/bin/clang\" /p:UsingToolMicrosoftNetCompilers=false /p:NoPgoOptimize=true --portablebuild false /p:DotNetBuildFromSource=true /p:DotNetBuildSourceOnly=true /p:DotNetBuildTests=true --runtimeconfiguration Release --librariesConfiguration Debug /p:PrimaryRuntimeFlavor=Mono --warnAsError false /p:TargetRid=linux-s390x --subset clr+mono+libs+host+packs+libs.tests --test > log", cwd=repo_dir)

def send_email_via_relay(smtp_server, smtp_port, sender_email, recipient_email, subject, body, log_file_path):
    # Create a multipart message
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = recipient_email
    msg['Subject'] = subject


    # Attach the log file
    with open(log_file_path, "rb") as attachment:
        content = attachment.read()
        part = MIMEBase("application", "octet-stream")
        part.set_payload(content)
        encoders.encode_base64(part)
        part.add_header(
            "Content-Disposition",
            f"attachment; filename= runtime-log-"+datetime.now().strftime("%Y-%m-%d")+".txt",
        )
        msg.attach(part)

    string_search = b'Build FAILED'

    if string_search in content:
        body += "\n Summary: The Build has Failed! . Please fix the errors"
    else:
        body += "\n Summary: The Build is Successful :)"

    # Add body to email
    msg.attach(MIMEText(body, 'plain'))

    try:
        # Connect to the SMTP server
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            # Send the email
            server.sendmail(sender_email, recipient_email, msg.as_string())
            print("Email sent successfully.")
    except Exception as e:
        print(f"Failed to send email. Error: {str(e)}")

#clean once everything is done

def clean():
    run_command("rm -rf runtime/ dotnet-custom-sdk/")

def main():
    repo_url = "https://github.com/dotnet/runtime.git"
    branch = "release/9.0"
    repo_dir = "runtime"

#   install_dependencies()
    clone_repository(repo_url, branch)
    
    global_version = get_dotnet_version("runtime")
    latest_tag = download_extract_sdk()
    build_and_test_mono_runtime(repo_dir)

#enter IBM's smtp relay server

    smtp_server = "<redacted>"
    smtp_port = 25

    sender_email = "runtime-cronjob"

#enter recipient email address
    
    recipient_email = "<redacted>"
    subject = "RUN  "+ datetime.now().strftime("%Y-%m-%d")
    body = "Please find the log file attached.\n SDK_GLOBAL_JSON_VERSION = {} \n SDK_RELEASE_VERSION = {}".format(global_version,latest_tag)
    log_file_path = "runtime/log"

    send_email_via_relay(smtp_server, smtp_port, sender_email, recipient_email, subject, body, log_file_path)

    clean()

if __name__ == "__main__":
    main()

