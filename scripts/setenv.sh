#!/bin/bash
# These need to be set for CodeChecker to work for some build systems
export LD_LIBRARY_PATH="$LD_LIBRARY_PATH"
export LD_PRELOAD="$LD_PRELOAD"
export CC_LOGGER_GCC_LIKE="gcc:/bin/g++:clang:clang++:cc:c++"
export CC_LOGGER_FILE="$CC_LOGGER_FILE"

# Some tools used in the framework
export LOC_COUNTER_PATH=$(which cloc)
export COMPLEXITY_TOOL=$(which pmccabe)

export PATH="$(pwd):$PATH"


log_bazel_build()
{
  CodeChecker log -o "$1" -b \
  "bazel --batch \
   build \
     --spawn_strategy=local \
     --strategy=Genrule=local \
     --action_env=LD_PRELOAD=\$LD_PRELOAD \
     --action_env=LD_LIBRARY_PATH=\$LD_LIBRARY_PATH \
     --action_env=CC_LOGGER_GCC_LIKE=\$CC_LOGGER_GCC_LIKE \
     --action_env=CC_LOGGER_FILE=\$CC_LOGGER_FILE \
   $2"
}