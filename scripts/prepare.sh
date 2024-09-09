#!/bin/bash
## Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
## SPDX-License-Identifier: Apache-2.0

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
