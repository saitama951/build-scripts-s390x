#!/bin/bash

set -x

BASEDIR=$(pwd)
message=()
version=""
commit_id=""
export CROSS_ARCH=s390x
export CROSSCOMPILE=1
export ROOTFS_DIR=${BASEDIR}/s390x-rootfs

function clone_dotnet {
        git clone --branch ${1:-main} https://github.com/dotnet/dotnet
        pushd dotnet
        commit_id=$(git show HEAD --pretty=format:"%h" --no-patch)
        message+=("commit id:- ${commit_id} <br>")
        popd
}

function install_cross_rootfs {
	pushd dotnet/src/runtime/eng/common/cross
	sudo ./build-rootfs.sh s390x --rootfsdir ${BASEDIR}/s390x-rootfs
	popd
}

function build_dotnet {
    pushd dotnet
	dotnet_build_flags=(
		--source-only 
		--online 
		--use-mono-runtime
		"/p:TargetArchitecture=s390x"
		"/p:PortableBuild=true"
        )
	./prep-source-build.sh
	./build.sh "${dotnet_build_flags[@]}"
    popd
}

run=(clone_dotnet install_cross_rootfs build_dotnet)

for project in "${run[@]}"; do
        eval "${project}"
done

