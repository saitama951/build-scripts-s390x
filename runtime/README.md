#dependencies
* gh
* git-lfs
* toolchain to build runtime

#Functionalities

* clones the dotnet/runtime repo. and validates if the dotnet sdk version present in the global.json is present on the machine or not
* if not then it would download all the dotnet-sdk and nupkg's relating to it from IBM/dotnet-s390x/releases. (make sure you have gh installed and have configure `gh auth login` (required to download the nupkg's))
* just run `python3 automate-runtime.py`

#TO-DO
* validate `gh auth status`
* if the corresponding sdk is not present in IBM/dotnet-s390x/releases .automate the whole cross building process on x86 by using qemu.
* provide a pretty menu to command line args if specific commit or branch is to be built.
* maintain a patch file where intermediate workaround's can be applied through the script (i.e libs.test hangs issue)
