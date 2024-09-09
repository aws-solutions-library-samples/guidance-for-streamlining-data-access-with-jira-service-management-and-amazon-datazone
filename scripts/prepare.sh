#!/bin/bash
# MIT No Attribution

# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the "Software"), to deal in
# the Software without restriction, including without limitation the rights to
# use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
# the Software, and to permit persons to whom the Software is furnished to do so.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
# FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
# COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
# IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

# Check if the correct number of arguments are provided
if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <dz_domain_id>"
    exit 1
fi

# Assigning command line arguments to variables
dz_domain_id="$1"

# Array of files to perform replacements in
files=(
    "config/DataZoneConfig.ts"
    # Add more files here if needed
)

# Loop through the array of files and perform replacements
for file in "${files[@]}"; do
    # Check if the file exists
    if [ ! -f "$file" ]; then
        echo "Error: File '$file' not found."
        continue
    fi
    
    # Perform the string replacements using sed
    sed -i "" "s/DZ_DOMAIN_ID_PLACEHOLDER/$dz_domain_id/g" "$file"

    echo "Replacements performed in '$file'."
done
