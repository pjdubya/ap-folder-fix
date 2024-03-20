import argparse
import logging
import os
import re
import shutil
from datetime import datetime

# Ensure logs directory exists
logs_dir = 'logs'
os.makedirs(logs_dir, exist_ok=True)

# Configure the root logger
script_name = os.path.splitext(os.path.basename(__file__))[0]
current_date = datetime.now().strftime("%Y%m%d")
log_file = os.path.join(logs_dir, f"{script_name}.{current_date}.log")
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', filename=log_file, filemode='a')  # Change filemode to 'a' for append

# Create a console handler and set its level to INFO
console = logging.StreamHandler()
console.setLevel(logging.INFO)

# Create a formatter and set the format for the console handler
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
console.setFormatter(formatter)

# Add the console handler to the root logger
logging.getLogger('').addHandler(console)

def move_files(input_folder):
    date_pattern = re.compile(r'^\d{4}-\d{2}-\d{2}$')

    for root, dirs, files in os.walk(input_folder):

        # only process this folder if folder name is a date in the format "YYYY-MM-DD"
        if not re.match(date_pattern, os.path.basename(root)):
            # first make sure we dont process any other dirs in the root too if we're not at the top level folder
            if root != input_folder:
                dirs.clear()
            continue

        for folder in dirs:
            if folder == "FLAT":
                flatwizard = True
                date_folder = os.path.basename(root)
                flat_target_folder = os.path.join(input_folder, "_FlatWizard", "DATE_" + date_folder, "FLAT")
                os.makedirs(flat_target_folder, exist_ok=True)
                flat_source_folder = os.path.join(root, folder, "FlatWizard")
                # handle both cases where FlatWizard is a subfolder of FLAT or flats are directly in FLAT
                if not os.path.exists(flat_source_folder):
                    flat_source_folder = os.path.join(root, folder)
                    flatwizard = False
                if not os.path.exists(flat_source_folder):
                    logging.error(rf"Error: FlatWizard directory not found: {flat_source_folder}")
                else:
                    for file in os.listdir(flat_source_folder):
                        file_path = os.path.join(flat_source_folder, file)
                        logging.info(rf"Moving {file_path} to {flat_target_folder}")
                        shutil.move(file_path, flat_target_folder)
                
                # remove the empty FlatWizard folder
                if flatwizard:
                    logging.info(rf"Removing {flat_source_folder}")
                    os.rmdir(flat_source_folder)
                # remove the empty FLAT folder
                logging.info(rf"Removing FLAT {os.path.join(root, folder)}")
                os.rmdir(os.path.join(root, folder))
                
            elif folder == "LIGHT":
                date_folder = os.path.basename(root)
                lights_folder = os.path.join(root, folder)
                for subfolder in os.listdir(lights_folder):
                    subfolder_path = os.path.join(lights_folder, subfolder)
                    if os.path.isdir(subfolder_path):   #presumably a target folder
                        subfolder_date_folder = os.path.join(input_folder, subfolder, "DATE_" + date_folder, "LIGHT")
                        os.makedirs(subfolder_date_folder, exist_ok=True)
                        for file_or_dir in os.listdir(subfolder_path):
                            # if file_or_dir is direcotry named "WBPP", move it to subfolder_path
                            if file_or_dir == "WBPP":
                                target_folder = os.path.join(input_folder, subfolder)
                                wbpp_folder = os.path.join(subfolder_path, file_or_dir)
                                logging.info(rf"Moving WIP dir {wbpp_folder} to target dir {target_folder}")
                                shutil.move(wbpp_folder, target_folder)
                            else:
                                file_or_dir_path = os.path.join(subfolder_path, file_or_dir)
                                logging.info(rf"Moving {file_or_dir_path} to {subfolder_date_folder}")
                                shutil.move(file_or_dir_path, subfolder_date_folder)
                        # remove the empty subfolder
                        logging.info(rf"Removing {subfolder_path}")
                        os.rmdir(subfolder_path)
                # remove the empty LIGHT folder
                logging.info(rf"Removing LIGHT {lights_folder}")
                os.rmdir(lights_folder)
            else:
                logging.error(rf"Error: Unknown folder found: {root}\\{folder}")

        # need to decide what to do with files in any of these locations by logging them for manual handling later
        for file in files:
            logging.info(rf"skipping file: {root}\\{file}")


        # check if root directory contains any files or folders and remove it if empty            
        if os.listdir(root) == []:
            logging.info(rf"Removing {root}")
            os.rmdir(root)            

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--localpath", type=str, help="Path to location on local machine where files are stored")
    args = parser.parse_args()

    logging.info(f"Starting script {__file__} with args: {args}")

    if args.localpath:
        move_files(args.localpath)
    else:
        logging.error("Must provide valid path using --localpath parameter")
