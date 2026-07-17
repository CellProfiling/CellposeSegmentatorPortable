import argparse
import datetime
import logging
import os
import cv2
import yaml
import cellpose_segmentation
from cellposesegmentator import image_utils
from cellpose import models

def main():
    # This is the log configuration. It will log everything to a file AND the console
    logging.basicConfig(filename='log.txt', encoding='utf-8', format='%(levelname)s: %(message)s', filemode='w', level=logging.INFO)
    console = logging.StreamHandler()
    logging.getLogger().addHandler(console)
    logger = logging.getLogger("Cellpose segmentation")

    # This is the general configuration variable. We are going to use the special key "log" in the dictionary to use the log in our code
    config = { "log": logger}

    # If you want to use constants with your script, add them here
    config["nuclei_only"] = False
    config["nuc_diameter"] = 200
    config["cyto_diameter"] = 1000

    # If your nuclei image is too dim or heavily influenced by light gradients you might want to normalize it to make the cellpose segmentation more reliable
    config["normalize_nuclei"] = True

    # Set use_cpsam = True to run CellposeSAM (single 3-channel inference) instead of
    # two separate cyto3 calls. Requires the 'cpsam' pretrained model to be available.
    config["use_cpsam"] = False
    config["gpu"] = False

    # config.yaml overrides the constants above (must exist, may be empty)
    with open("../config.yaml", "r") as file:
        config_contents = yaml.safe_load(file)
        if config_contents:
            config = config | config_contents

    # CLI args override config.yaml. No defaults here, so unset args stay None and don't clobber
    argparser = argparse.ArgumentParser(description="Please input the following parameters")
    argparser.add_argument("--nuclei_only", help="only segment nuclei (skip cytoplasm)", action=argparse.BooleanOptionalAction)
    argparser.add_argument("--nuc_diameter", help="average nuclei diameter in pixels", type=int)
    argparser.add_argument("--cyto_diameter", help="average cell diameter in pixels", type=int)
    argparser.add_argument("--normalize_nuclei", help="normalize dim/uneven nuclei before segmentation", action=argparse.BooleanOptionalAction)
    argparser.add_argument("--use_cpsam", help="use CellposeSAM backend instead of cyto3", action=argparse.BooleanOptionalAction)
    argparser.add_argument("--gpu", help="use a CUDA-capable GPU if available", action=argparse.BooleanOptionalAction)
    args = argparser.parse_args()
    config = config | {key: value for key, value in vars(args).items() if value is not None}

    # Log the start time and the final configuration so you can keep track of what you did
    config["log"].info('Start: ' + datetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S"))
    config["log"].info('Parameters used:')
    config["log"].info(config)
    config["log"].info('----------')


    # We load the model (abort the whole run if it fails: nothing to do without a model)
    try:
        model_nuc = models.CellposeModel(gpu=config["gpu"], model_type='nuclei')
        config["log"].info("Requested GPU: " + str(config["gpu"]) + " | effective device: " + str(model_nuc.device))
        if config["gpu"] and not model_nuc.gpu:
            config["log"].warning("GPU requested but not available: falling back to CPU")
        model_cyto = None
        model_cpsam = None
        if config["use_cpsam"]:
            model_cpsam = models.CellposeModel(pretrained_model='cpsam', gpu=config["gpu"])
            config["log"].info('Using CellposeSAM (cpsam) for cell segmentation')
        else:
            model_cyto = models.CellposeModel(gpu=config["gpu"], model_type='cyto3')
            config["log"].info('Using cyto3 for cell segmentation')
    except Exception as err:
        config["log"].error("Failed to load the Cellpose model: " + str(err))
        raise

    # If we provide a "path_list.csv" file, we run our code for each pair of input/output sub-folders
    if os.path.exists("../path_list.csv"):
        with open("../path_list.csv", 'r') as f:
            path_list = f.readlines()

        for curr_set in path_list:
            if curr_set.strip() != "" and not curr_set.startswith("#"):
                # Isolate each FOV: one bad row logs and is skipped, the batch continues
                try:
                    curr_set_arr = curr_set.split(",")
                    os.makedirs(curr_set_arr[3].strip(), exist_ok=True)
                    nuclei_img = image_utils.read_grayscale_image(curr_set_arr[0].strip())
                    cyto_img1 = None
                    cyto_img2 = None
                    if not config["nuclei_only"]:
                        cyto_img1 = image_utils.read_grayscale_image(curr_set_arr[1].strip())
                        if curr_set_arr[2].strip() != "":
                            cyto_img2 = image_utils.read_grayscale_image(curr_set_arr[2].strip())

                    cellpose_segmentation.segment(model_nuc, model_cyto, nuclei_img, cyto_img1, cyto_img2, config["nuc_diameter"], config["cyto_diameter"], curr_set_arr[3].strip(), curr_set_arr[4].strip(), model_cpsam=model_cpsam, use_cpsam=config["use_cpsam"], normalize_nuclei=config["normalize_nuclei"])

                    config["log"].info("- Saved results for " + curr_set_arr[4].strip())
                except Exception as err:
                    config["log"].error("Failed to process '" + curr_set.strip() + "': " + str(err))
                    continue


    config["log"].info('----------')
    config["log"].info('End: ' + datetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S"))
