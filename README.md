# query-gpuinfo-data

## License

This software is not presently released under a license.

The data in `data/` is obtained under `CC BY 4.0` as specified there.

`vk.xml` comes from <https://github.com/KhronosGroup/Vulkan-Headers/blob/main/registry/vk.xml>
and is licensed according to the license in that file.

## Getting the code

`git clone --recurse-submodules https://github.com/kainino0x/gpuinfo-vulkan-query.git`

or if you have already cloned, just get the submodule

`git submodule update --init`

To update, `git pull` (and if you have an older version of Git, update
submodules again).

## Querying the data

Edit and run the "Requirements" section of `query.py` as needed.
The requirements are applied iteratively: each one is only "blamed" for losing
devices not already lost by previous requirements.

To understand how the reports are structured, use `data/sample-report-10954.json`
as an example (which has been pretty-printed to be readable).
