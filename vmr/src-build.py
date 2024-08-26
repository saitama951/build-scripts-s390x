import os
import subprocess
import sys
import json
import select
def run_command(command, cwd=None):
    """Run a shell command."""
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

def install_dependencies():
    """Install the necessary dependencies for building the source build."""
    print("Installing dependencies...")
    dependencies = [
        "sudo apt-get update",
        "sudo apt-get install -y git clang cmake ninja-build libicu-dev libssl-dev libcurl4-openssl-dev zlib1g-dev"
    ]
    for dep in dependencies:
        run_command(dep)

def clone_repository(repo_url, branch="main"):
    """Clone the dotnet/dotnet repository."""
    target_dir="dotnet"
    if not os.path.exists(target_dir):
        print(f"Cloning repository from {repo_url}...")
        run_command(f"git clone --branch {branch} {repo_url}")
    else:
        print(f"Repository already exists at {target_dir}. Skipping clone step.")

def checkout_branch(branch, repo_dir):
    """Checkout the specified branch."""
    print(f"Checking out branch {branch}...")
    run_command(f"git checkout {branch}", cwd=repo_dir)

def get_dotnet_version(repo_dir):
    """Retrieve the .NET version from the global.json file."""
    global_json_path = os.path.join(repo_dir, "global.json")
    
    if not os.path.exists(global_json_path):
        print(f"Error: global.json not found in {repo_dir}")
        return None
    
    with open(global_json_path, 'r') as file:
        data = json.load(file)
    
    try:
        version = data['tools']['dotnet']
        print(f".NET SDK version in global.json: {version}")
        return version
    except KeyError:
        print("Error: Version information not found in global.json")
        return None

def validate_install_dotnet_version():
    """Get the installed .NET SDK version on the system."""
    print("Checking installed .NET SDK version...")
    version_output = run_command("dotnet --version")
    global_version = get_dotnet_version("dotnet")
    if version_output !=0:
        if not os.path.exists("/root/dotnet/.dotnet"):
            run_command("mkdir .dotnet/", cwd="dotnet")
        download_extract_sdk(global_version)
        return global_version

    if global_version == version_output:
        print("The .NET SDK version matched the installed version.")
    else:
        print(f"Version mismatch: global.json specifies {global_version}, but {version_output} is installed.")
        download_extract_sdk(global_version)

    return global_version

def download_extract_sdk(global_version):
    print("downloading the dotnet-sdk version %s" % global_version)
    success = run_command("wget https://github.com/IBM/dotnet-s390x/releases/download/v%s/dotnet-sdk-%s-linux-s390x.tar.gz" %(global_version,global_version))
    if success != 0:
        print("This sdk version is not present in the IBM/dotnet-s390x/releases please build it manually!")
        sys.exit()
    print("downloading corresponding arch nupkgs")
    run_command("mkdir packages")
    run_command("gh release download v%s --repo IBM/dotnet-s390x --pattern \"*linux-s390x*.nupkg\"" %(global_version),cwd="packages")
    run_command("tar -xzf dotnet-sdk-%s-linux-s390x.tar.gz --directory dotnet/.dotnet/" % global_version)
    run_command(".dotnet/dotnet nuget add source /root/packages", cwd="dotnet")

def build_mono_vmr(repo_dir):
    """Build the Mono runtime for s390x."""
    print("Building the mono vmr for s390x...")
    run_command("./prep-source-build.sh", cwd=repo_dir)
    run_command("tar -xzf ./prereqs/packages/archive/*.tar.gz --directory ../packages", cwd=repo_dir)
    run_command("./build.sh --with-sdk ./.dotnet/ --with-packages /root/packages --source-only --use-mono-runtime", cwd=repo_dir)

def main():
    repo_url = "https://github.com/dotnet/dotnet.git"
    repo_dir = "dotnet"
  
  try:
        branch = sys.argv[2]
    except IndexError:
        branch = "main"

   # if sys.argv[1] == "--branch":
    #    branch = sys.argv[2]

#    install_dependencies()
    clone_repository(repo_url, branch)
#    checkout_branch(branch, repo_dir)
    
    validate_install_dotnet_version()
    
    build_mono_vmr(repo_dir)

if __name__ == "__main__":
    main()

