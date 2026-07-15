Cellpose segmentation
=====================

This program, built upon the base template, wraps and runs the Cellpose segmentation model in a convenient way. It can run nuclei, nuclei + cytoplasm or nuclei + 2 x cytoplasm [combined] segmentation over grayscale images.

Two segmentation backends are supported:
- **cyto3** (default): runs Cellpose cyto3 separately on each cytoplasm channel, then merges the results using the custom merge algorithm (primary channel fills cells, secondary fills gaps).
- **CellposeSAM** (optional): runs a single CellposeSAM (cpsam) forward pass on a 3-channel stack (nuclear + cyto1 + cyto2), then applies the same custom merge logic. Because the model sees all channels at once, no secondary gap-fill pass is needed.



Requirements
------------

Please read the overall `README.md` file to understand the structure principles of this code.



Installation
------------

- Install the code following the steps indicated in the overall `README.md` file, just remember to use all the contents of this directory as you working code.



Setup
-----

The segmentation parameters can be set in three layers, each overriding the previous one:

**constants < `config.yaml` < command-line arguments**

1. **Constants (defaults)** — edit the `config[...]` lines near the top of `process.py`:
   - `config["nuclei_only"] = False` — set `True` to segment only nuclei (skip cytoplasm).
   - `config["nuc_diameter"] = 200` — average nuclei diameter in pixels.
   - `config["cyto_diameter"] = 1000` — average cell diameter in pixels.
   - `config["normalize_nuclei"] = True` — set `True` for dim or unevenly-exposed nuclei (see **Nuclei normalization** below).
   - `config["use_cpsam"] = False` — set `True` for the CellposeSAM backend instead of cyto3 (see **Segmentation backends** below).
   - `config["gpu"] = False` — set `True` if you have a CUDA-capable GPU available and want to use it.

2. **`config.yaml`** — overrides the constants without editing code. This file **must exist** (it may be empty). Uncomment and edit keys as needed, e.g.:
   ```yaml
   nuc_diameter: 150
   gpu: true
   ```

3. **Command-line arguments** — override everything, for one-off runs. Boolean options use the `--flag` / `--no-flag` form:
   ```
   python process.py --gpu --nuc_diameter 150 --no-normalize_nuclei
   ```
   Available: `--nuclei_only`/`--no-nuclei_only`, `--nuc_diameter N`, `--cyto_diameter N`, `--normalize_nuclei`/`--no-normalize_nuclei`, `--use_cpsam`/`--no-use_cpsam`, `--gpu`/`--no-gpu`.

To run Cellpose segmentation you have to gather the information about the sets of images you want to process. Cellpose segmentation reads `path_list.csv` to locate each set of images, in the following .csv format:

`nuclei_image,cyto_image1,cyto_image2,output_folder,output_prefix`

- `nuclei_image`: the nuclei targeting marker FOV image.
- `cyto_image1`: the cytoplasm targeting marker FOV image. It can be microtubuli, ER, etc... Leave it blank if you want to segment only the nuclei.
- `cyto_image2`: the cytoplasm targeting marker FOV image. It can be microtubuli, ER, etc... Leave it blank if you want to segment only the nuclei or use 1 single cytoplasm marker.
- `output_folder`: the base folder that will contain all generated segmentations.
- `output_prefix`: the prefix appended to all files generated per cell.

All images can be relative or absolute paths, or directly URLs. You can also skip lines between runs with the special character `#` in front of the desired lines.
Check the following `path_list.csv` content as an example:

```
#nuclei_image,cyto_image1,cyto_image2,output_folder,output_prefix
input/nuc1.tif,input/mt1.tif,,output,example1_
#input/nuc2.tif,input/mt2.tif,,output,example2_
input/nuc3.tif,input/mt3.tif,,output,example3_
```



Segmentation backends
---------------------

### cyto3 (default)

`config["use_cpsam"] = False`

Runs Cellpose cyto3 independently on each cytoplasm channel, guided by the nuclear mask. The two resulting masks are merged using the custom algorithm: cyto1 fills cell regions first, cyto2 patches any remaining gaps, and nuclear pixels always take priority. Best choice when your cytoplasm channels have variable signal quality across cells.

### CellposeSAM

`config["use_cpsam"] = True`

Replaces the two separate cyto3 calls with a single CellposeSAM (cpsam) inference on a 3-channel stack (nuclear, cyto1, cyto2). The model processes all channels simultaneously, so it can detect cells that would be missed by either channel alone. The custom merge step still runs afterward to split any regions containing multiple nuclei and to enforce nuclear pixel priority, but the secondary gap-fill pass is skipped since it is no longer needed. If only one cytoplasm channel is provided, the third channel is filled with zeros.

**Requirements:** CellposeSAM requires Cellpose 4.x, which is not installed by default (the default `requirements.txt` pins `cellpose==3.1.1.1` for faster CPU inference). To use this backend, upgrade manually:

```
pip install cellpose==4.1.1
```

Cellpose 4.1.1 has been tested with this code. Note that Cellpose 4 is significantly slower than Cellpose 3 on CPU — a GPU is strongly recommended when using this backend.



Nuclei normalization
--------------------

`config["normalize_nuclei"] = False`

By default the nuclei image is passed to Cellpose as-is (relying on Cellpose's own percentile normalization). This works well for typical, evenly-exposed nuclei images.

Set `config["normalize_nuclei"] = True` for challenging nuclei channels — very dim signal, or a wide intensity spread where bright nuclei and faint nuclei coexist and the faint ones get missed. When enabled, the nuclei image is preprocessed before segmentation:

1. A minor Gaussian blur (sigma 1.0) to tame noise.
2. A gamma compression (exponent 0.35) that squashes the bright/dim dynamic range so faint and bright nuclei end up at a similar intensity, giving the model a fair chance to detect all of them. The white point is set at the 99th percentile to ignore hot-pixel outliers.

Cellpose's internal normalization is disabled in this mode, since the image is already scaled to `[0, 1]`.

A quality-control image, `[output_prefix]nuclei_normalized.jpg` (a lightweight JPG), is saved to the output folder so you can inspect exactly what the model received. If dim nuclei are still missed, lowering the gamma exponent (e.g. from 0.35 to 0.25 in `cellpose_segmentation.py`) compresses the dynamic range more aggressively.



Running the code
----------------

**NOTE**: remember that you have to access your created virtual environment before running the code! To do so, navigate to the directory you created and activate it.
 - Example:
   - `cd /home/lab/sandbox/example`
   - `source bin/activate`

Once you have activated your virtual environment and modified all the desired parameters (see section **Setup**), just run the code with `python process.py`. OBS: you have to run the `process.py` file, which will in turn call the rest of the code.



Output
------

Cellpose segmentation generates in the chosen output_folder the following files:

If `config["normalize_nuclei"] = True`, an extra quality-control file is also saved in both modes:
- `[output_prefix]nuclei_normalized.jpg`: the normalized nuclei image (lightweight JPG) that was fed to the nuclei model. For visual inspection only.

**cyto3 mode:**
- `[output_prefix]nuclei_mask.png`: labeled image with the Cellpose nuclei segmentation.
- `[output_prefix]cyto1_mask.png`: labeled image with the Cellpose cyto1 marker segmentation.
- `[output_prefix]cyto2_mask.png`: labeled image with the Cellpose cyto2 marker segmentation (only if cyto_image2 was provided).
- `[output_prefix]cell_mask.png`: labeled image with the final merged cell segmentation. (This is probably the one you want)

**CellposeSAM mode:**
- `[output_prefix]nuclei_mask.png`: labeled image with the Cellpose nuclei segmentation.
- `[output_prefix]sam_raw_mask.png`: labeled image with the raw CellposeSAM output before merging.
- `[output_prefix]cell_mask.png`: labeled image with the final merged cell segmentation. (This is probably the one you want)
