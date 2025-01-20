set -x

BASEDIR=$(pwd)
message=()
version=""
commit_id=""
function clone_runtime {
	git clone --branch ${1:-main} https://github.com/dotnet/runtime
	pushd runtime
	commit_id=$(git show HEAD --pretty=format:"%h" --no-patch)
	message+=("commit id:- ${commit_id}")
	popd
}

function extract_sdk {

	version=$(jq .sdk.version ${BASEDIR}/runtime/global.json)
	version="${version%\"}"
	version="${version#\"}"
	mkdir ${BASEDIR}/runtime/.dotnet/
	tar -xzf ${BASEDIR}/sdk/dotnet-sdk-$version-linux-s390x.tar.gz --directory ${BASEDIR}/runtime/.dotnet/
	if [ $? -ne 0 ]; then
		pushd sdk
		gh release download v${version} --repo IBM/dotnet-s390x --pattern dotnet-sdk-${version}-linux-s390x.tar.gz
		popd
		if [ $? -ne 0 ]; then
			message+=("failed to get the dotnet runtime. please build the sdk with version ${version}")
			return 1
		fi
		pushd packages
		gh release download v$version --repo IBM/dotnet-s390x --pattern '*linux-s390x*.nupkg'
		tar -xzf ${BASEDIR}/sdk/dotnet-sdk-$version-linux-s390x.tar.gz --directory ${BASEDIR}/runtime/.dotnet/
		popd
	fi
}

function build_runtime {
	pushd runtime
	runtime_build_flags=(
		# llvm bug https://github.com/llvm/llvm-project/issues/109113
		--cmakeargs -DCMAKE_CXX_COMPILER=\"/home/sanjam/llvm-project/build/bin/clang++\" 
		--cmakeargs -DCMAKE_C_COMPILER=\"/home/sanjam/llvm-project/build/bin/clang\"
		--portablebuild false
		--runtimeconfiguration Release 
		--librariesConfiguration Debug 
		--warnAsError false 
		"/p:NoPgoOptimize=true"
		"/p:UsingToolMicrosoftNetCompilers=true"
		"/p:TreatWarningsAsErrors=false"
		"/p:DotNetBuildFromSource=true"
		"/p:DotNetBuildSourceOnly=true" 
		"/p:DotNetBuildTests=true"
		"/p:PrimaryRuntimeFlavor=Mono" 
		"/p:TargetRid=linux-s390x"
		--subset clr+mono+libs+host+packs+libs.tests
		--test
	)

	./build.sh "${runtime_build_flags[@]}" > log

	if [ $? -ne 0 ]; then
		message+=("build failed! please check the errors")
	else
		message+=("build succeess!")
	fi

	popd
}

function shoot_email {
	pushd runtime
	recipents_emails=(
	)
	file=$(mktemp)
	timestamp=i$(date)
	echo "${message[@]}" > file
	mutt -s "RUN ${timestamp}" -a "log" -- "${recipents_emails[@]}" < file
	rm -rf file
	popd	
}

run=(clone_runtime extract_sdk build_runtime shoot_email)

for project in "${run[@]}"; do
	eval "${project}"
done
