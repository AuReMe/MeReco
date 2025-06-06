#!/home/genouest/dyliss/norobert/miniconda3/envs/prolific/bin python3
# -*- coding: utf-8 -*-

"""
Created on Mon Apr 14 2025

@author: norobert
"""

import os
import glob
import argparse
import gzip
import pandas as pd
from pathlib import Path
import numpy as np
import time

# FUNCTIONS ---------------------------------------------------------------------------------

## UTILS ------------------------------------------------------------------------------------
def parser() : 
    parser = argparse.ArgumentParser(description="Prolipipe pipeline for large-scale assessment of metabolic profiles on bacteria focusing on specific pathways.")
    
    ## arguments 
    parser.add_argument("-i", "--input", required=True, dest="input",help="Path to the folder where the genomes are")
    parser.add_argument("-o", "--output", required=True, dest="output",help="Path to the folder where you want to put the results in")
    parser.add_argument("--tax", required=True, dest="taxfile",help="path of the taxon file (.tsv)")
    parser.add_argument("--padmet_ref", required=True, dest="path_to_padmet_ref", help="Path to the reference database in Padmet format.")
    parser.add_argument("--ptsc", required=True, dest="ptsc", help="Path to root folder (for construction of Singularity bridge, necessary to access distant files).")
    parser.add_argument("--ptsi", required=True, dest="ptsi", help="Path to the singularity image of mpwt to use.")
    
    ## options
    parser.add_argument("--annot", dest="annot", default="prokka", help="Annotation tool(s) to use between 'prokka' (default), 'eggnog' and 'bakta'. If several annotation tools to use, write them comma-separated.")
    parser.add_argument("--egg_path",dest="egg_path",help="Path to the eggnog database, mandatory if you want to use eggnog as annotation tool.")
    parser.add_argument("--bak_path",dest="bak_path",help="Path to the bakta database, mandatory if you want to use bakta as annotation tool.")
    parser.add_argument("-c","--cpus", dest="cpus", default=20, help="Give the number of available CPUs")
    parser.add_argument("-k","--keep", dest="to_keep", default="", help="Give the file formats to keep - comma-separated list, '.' included")

    ## flags    
    parser.add_argument("-q", "--quick", action="store_true", dest="quick", help="Bypass most of the computation if results files are already generated")

    return parser.parse_args()


def my_basename(file):
    """
        Shorter version to get a basename (file name without path or extension)
    """
    return os.path.splitext(os.path.basename(file))[0]


def missing_or_empty(file_path):
    return not os.path.exists(file_path) or os.stat(file_path).st_size == 0


def decompress_gzip_file(file_path, extension, suppr_zip):
    """
        Uncompress a gzipped file 
        Input : 
            file_path (str) : path to the file 
            extension (str) : expected extension on final file (starting with ".")
            suppr_zip (bool) : whether to delete zipped archive or not
        Output : 
            the unzipped file 
    """
    ## get directory path, file basename and uncompressed file name
    dir_path = os.path.dirname(file_path)
    name = my_basename(dir_path)
    file_out = os.path.join(dir_path, name + extension)

    with gzip.open(file_path, 'rb') as f_in, open(file_out, 'wb') as f_out:
        f_out.write(f_in.read())
    if suppr_zip == True : 
        os.remove(file_path)  


def check_gzipped_only(genomes_dir) :
    """
        Check in a directory if subdirs contain gzipped files. If so,
        checks if no fasta available. if so, uncompress the gzipped and 
        attributes it a fasta extension. 
        Input : 
            genomes_dir (str) : path to the directory containing subdirs 
            containing genomes 
    """
    extension = ".fasta"
    subdirs = glob.glob (genomes_dir + "/*")
    for subdir in subdirs :

        ## get files and explore them
        files = glob.glob (subdir + "/*.*")
        if not any(file.endswith(extension) for file in files) :
            
            for file in files :
                ## check if an fna needs to be renamed
                if file.endswith(".fna") :
                    print(f"Renaming {file} to .fasta...")
                    move(file, file.replace(".fna", extension))
                    break 
                
                ## check if need to unzip
                if file.endswith(".gz") :
                    print(f"Uncompressing {file}...")
                    decompress_gzip_file(file, extension, False)
                    break
        
        ## rename fasta according to its directory
        else :
            for file in files :
                if file.endswith(extension) :
                    dir_path = os.path.dirname(file)
                    name = my_basename(dir_path)
                    file_out = os.path.join(dir_path, name + extension)
                    if file != file_out : 
                        move(file, file_out)


def bigprint(message): 
    delimitation = "-------------------------------------------"
    print(f"\n{delimitation}\n{message}\n{delimitation}\n")
    return


def move(source, dest):
    try:
        os.rename(source, dest)  # Déplace ou renomme le fichier/dossier
    except PermissionError:
        print(f"Some rights are missing to move {source} to {dest}")
    except FileExistsError:
        print(f"Destination {dest} already exists!")


def mkdir(path) : 
    if not os.path.exists(path):
        try :
            os.makedirs(path, exist_ok = True)
        except PermissionError:
            print("Some rights are missing to create {}".format(path))
        except Exception as e:
            print(f"An error occurred (mkdir): {e}")


def remove(list_path):
    for path in list_path:
        p = Path(path)
        if p.exists():
            if p.is_file() or p.is_symlink():
                p.unlink()  ## delete a file or link
            elif p.is_dir():
                for sub in p.glob("**/*"):  ## delete recursively
                    if sub.is_file() or sub.is_symlink():
                        sub.unlink()
                    elif sub.is_dir():
                        os.rmdir(sub)  ## delete empty dir
                os.rmdir(p)  ## delete main dir 

## KEY-FUNCTIONS -----------------------------------------------------------------------------

def prokka_annotation(input_dir, output_path, options) : 
    """
    Prokka annotation step : from a fasta file, generate a GBK file of annotated genome. Iterated on all genomes
    Inputs : 
        input_dir (str) : path to genomes to process
        output_path (str) : path to Prolipipe's output 
        options (parser) : arguments from parser
    Output : 
        processed (list) : list of processed genomes' names
    """
    print("Prokka annotation launched.\n")
    mkdir(os.path.join(output_path, 'prokka'))
    processed = pd.DataFrame(columns = ['genome', "prokka"])

    for genome_name in os.listdir(input_dir) : 
        prok_file = os.path.join(output_path, "prokka", genome_name, genome_name)

        if missing_or_empty(prok_file + ".gbk"):
            ## launch annotation
            command_pro = f"prokka {input_dir}{genome_name}/{genome_name}.fasta --outdir {output_path}prokka/{genome_name} --prefix {genome_name} --compliant --force --cpus {options.cpus}"
            ## --compliant       Force Genbank/ENA/DDJB compliance
            bigprint(command_pro)
            os.system(command_pro)
            
            ## removing unused files
            unused_files=set([".ecn", ".err", ".ffn", ".fixed*", ".fsa", ".gff", ".log", ".sqn", ".tbl", ".val", ".faa "]) - set(options.to_keep.split(","))
            remove([f"{prok_file}{extension}" for extension in unused_files])

            ## rename and count processed genomes
            if os.path.exists(prok_file + ".gbf"):
                move(prok_file+".gbf",prok_file+".gbk")     # rename .gbf to .gbk
            if os.path.exists(prok_file + ".gbk"): 
                processed.loc[len(processed)] = [genome_name, "OK"]
    
    return processed
        

def eggnog_annotation(input_dir, output_path, options):
    """
    EggNOG-mapper annotation step : from a fasta file, generate a GBK file of annotated genome. Iterated on all genomes
    Inputs : 
        input_dir (str) : path to genomes to process
        output_path (str) : path to Prolipipe's output 
        options (parser) : arguments from parser
    Output : 
        processed (list) : list of processed genomes' names
    """
    print("Eggnog annotation launched.\n")
    path_to_egg = options.egg_path
    mkdir(os.path.join(output_path, 'eggnog'))
    processed = pd.DataFrame(columns = ['genome', "eggnog"])

    for genome_name in os.listdir(input_dir) :
        output_eggnog = os.path.join(output_path, "eggnog", genome_name)
        out_file = os.path.join(output_eggnog, genome_name + ".gbk")
        
        if missing_or_empty(out_file):
            ## annotation 
            mkdir(output_eggnog)
            genome = os.path.join(input_dir, genome_name, genome_name + ".fasta")
            command_egg = f"emapper.py -i {genome} -o {genome_name} --cpu {options.cpus} --itype genome --data_dir {path_to_egg} --output_dir {output_eggnog} --dbmem --genepred prodigal --override"
            bigprint(command_egg)
            os.system(command_egg)
            
            ## conversion of eggnog output to gbk
            prot = os.path.join(output_eggnog, genome_name + ".emapper.genepred.fasta")
            gff = os.path.join(output_eggnog, genome_name + ".emapper.genepred.gff")
            annot = os.path.join(output_eggnog, genome_name + ".emapper.annotations")
            command_egg2gbk = f'emapper2gbk genomes -fn {genome} -fp {prot} -g {gff} -a {annot} -o {out_file} -gt eggnog -c {options.cpus}'
            bigprint(command_egg2gbk)
            os.system(command_egg2gbk)

            ## rename and count processed genomes
            if os.path.exists(out_file):
                processed.loc[len(processed)] = [genome_name, "OK"]
    
    return processed 

def bakta_annotation(input_dir, output_path, options):
    """
    Bakta annotation step : from a fasta file, generate a GBK file of annotated genome. Iterated on all genomes
    Inputs : 
        input_dir (str) : path to genomes to process
        output_path (str) : path to Prolipipe's output 
        options (parser) : arguments from parser
    Output : 
        processed (list) : list of processed genomes' names
    """
    print("Bakta annotation launched.\n")
    path_to_bak = options.bak_path
    mkdir(os.path.join(output_path, 'bakta'))
    processed = pd.DataFrame(columns = ['genome', "bakta"])

    for genome_name in os.listdir(input_dir) :
        output = (os.path.join(output_path, "bakta", genome_name))
        final_file = os.path.join(output, genome_name + ".gbk")

        if missing_or_empty(final_file):
            ## annotate genomes 
            mkdir(output)
            fasta = (os.path.join(input_dir, genome_name, genome_name + ".fasta"))
            
            command = f"bakta --db {path_to_bak} {fasta} --output {output} --prefix {genome_name} --compliant --force --threads {options.cpus}"
            bigprint(command)
            os.system(command)
            ## --compliant      Force Genbank/ENA/DDJB compliance
            ## --force          Force overwriting existing output folder

            ## removing unused files
            unused_files = set([".embl", ".faa", ".ffn", ".fna", ".gff3", ".hypotheticals.faa", ".hypotheticals.ftsv", ".json", ".log", ".png", ".svg", ".tsv"]) - set(options.to_keep.split(","))   
            remove([os.path.join(output, genome_name + extension) for extension in unused_files])

            ## rename and count processed genomes
            if os.path.exists(os.path.join(output, genome_name + ".gbff")):
                move(os.path.join(output, genome_name + ".gbff"), final_file)
            if os.path.exists(final_file):
                processed.loc[len(processed)] = [genome_name, "OK"]
    
    return processed


def create_taxon_file(annotation, genomes, options):
    """
        From taxon file, generate another version of taxon file 
        interpretable for mpwt in each annotation tool directory
        Input : 
            annotation (list) : list of string corresponding to annotation tools
            genomes (list) : genomes names list
            options (parser) : arguments from parser
        Output : 
            a taxfile per annotool's directory
    """
    output_path = options.output
    taxfile = options.taxfile
    genomes = genomes.to_list()  

    df_taxons = pd.read_csv(taxfile, sep='\t')
    df_to_write = pd.DataFrame(columns = ["species", "taxon_id", "corresponding_file"])

    ## fill dfs
    col_taxon = df_taxons.columns[1]
    col_filename = df_taxons.columns[2]
    for index, row in df_taxons.iterrows() : 
        genome = row[col_filename]
        if genome in genomes :
            df_to_write.loc[len(df_to_write)] = [genome, row[col_taxon], genome]

    ## writing new file in each annotation subdir
    for annotool in annotation : 
        tax_file = os.path.join(output_path, annotool, 'taxon_id.tsv')
        df_to_write.to_csv(tax_file, sep="\t", index=False)  

def run_mpwt(output_path, annotation, genomes_names, options): 
    """
    Run mpwt on GBK files to generate PGDBs 
    Inputs : 
        output_path (str) : path to Prolipipe's output 
        annotation (list) : names of annotation tools used
        genomes_names (list) : list of genomes names to iterate on
        options (parser) : arguments from parser
    """
    path_to_scratch = options.ptsc
    path_to_singularity = options.ptsi
    mkdir(os.path.join(output_path, 'mpwt'))

    for annotool in annotation : 
        annotool_outdir = f"{output_path}mpwt/{annotool}/"
        mkdir(annotool_outdir)

        ## checking if mpwt has successfully run before
        path =  os.path.join(output_path, "mpwt", annotool)
        dat_dirs = [d for d in os.listdir(path) if os.path.isdir(os.path.join(path, d))]  ## lists subdirectories names                        ## filters for those which start with GCF
        print(f"Mpwt on {annotool} : {len(dat_dirs)} mpwt repositories found out of {len(genomes_names)} genomes to process")
        
        if len(dat_dirs) != len(genomes_names):
            command_mpwt = f"singularity exec -B {path_to_scratch}:{path_to_scratch} {path_to_scratch}{path_to_singularity} mpwt -f {output_path}{annotool}/ -o {annotool_outdir} --cpu {options.cpus} --patho --flat --clean --md -v"
            ## --patho : Launch PathoLogic inference on input folder
            ## --flat : Create BioPAX/attribute-value flat files
            ## --clean : Delete all PGDBs in ptools-local folder or only PGDB from input folder
            ## --md : Move the dat files into the output folder
            bigprint(command_mpwt)
            os.system(command_mpwt)
        else :
            print(f"    Nothing to process in {annotool_outdir}, moving on.\n")


def check_mpwt(df_summary, path):
    """
    Checks for all annotool referenced if they have .dat files in all subfolders
    Input :
        df_summary (pd.DataFrame) : global 
        path : path of checked dir
    Output : 
        True if no file is missing from any subdir (i.e. if there's no fail in annotation)
        a tuple (False, message) if any file is missing ; message is the error message 
    """
    annots = df_summary.columns[1:-1]

    for annotool in annots :
        genome_status = {}
        dir_annot = os.path.join(path, annotool)
        for genome in os.listdir(dir_annot) :
            to_search = os.path.join(dir_annot, genome, "*.dat")
            if len(glob.glob(to_search)) > 10 : 
                genome_status[genome] = "OK"
            else :
                genome_status[genome] = ""
        df_summary[f"mpwt_{annotool}"] = df_summary["genome"].map(genome_status)
    return df_summary


def check_padmet(df_summary, path):
    """
    Checks for all annotool referenced if they have all padmet files in all subfolders
    Input :
        df_summary (pd.DataFrame) : global 
        path : path of checked dir
    Output : 
        df_summary with updated padmet columns
    """

    annots = [col.replace("mpwt_", "") for col in df_summary.columns if "mpwt_" in col]
    new_cols = [f"padmet_{annotool}" for annotool in annots]
    
    ## intializing new coloumns
    for col in new_cols:
        if col not in df_summary.columns:
            df_summary[col] = None 

    for genome in sorted(os.listdir(path)):

        ## check if subdir is empty
        genome_path = os.path.join(path, genome)
        if not os.path.isdir(genome_path):
            continue 
        
        ## update df if file not empty
        for annotool in annots:
            padmet_file = os.path.join(genome_path, f"{genome}_{annotool}.padmet")
            if not missing_or_empty(padmet_file):
                df_summary.loc[df_summary['genome'] == genome, f"padmet_{annotool}"] = "OK"

    return df_summary


def convert2padmet(output_path, annotation, genomes_names, options):
    """
    Convert PGDBs in several .dat files into one strain-specific padmet file
    Inputs : 
        output_path (str) : path to Prolipipe's output 
        annotation (list) : names of annotation tools used
        genomes_names (list) : list of genomes names to iterate on
        options (parser) : arguments from parser
    """
    path_to_padmet_ref= options.path_to_padmet_ref
    path_to_scratch = options.ptsc
    path_to_singularity = options.ptsi
    padmet_output = output_path + 'padmet'
    mkdir(padmet_output)

    for annotool in annotation :
        dat_files = os.listdir(os.path.join(output_path, "mpwt", annotool))
        print(f"Checking before launching pgdb2padmet on {annotool} files : {len(dat_files)} files generated till now out of {len(genomes_names)} considered processable\n")
        for genome_name in genomes_names :
            print(f"testing if {os.path.join(padmet_output, genome_name, f'{genome_name}_{annotool}.padmet')} exists before launching padmet conversion" )
            if missing_or_empty(os.path.join(padmet_output, genome_name, f"{genome_name}_{annotool}.padmet")):
                
                ## create files in commune directories for annotations of the same genome 
                mkdir(os.path.join(padmet_output, genome_name))
                sing = os.path.join(path_to_scratch, path_to_singularity)
                pgdb = os.path.join(output_path, "mpwt", annotool, genome_name)
                output = os.path.join(padmet_output, genome_name, genome_name + "_" + annotool + ".padmet")
                command_pgdb2padmet_source = f"singularity run -B {path_to_scratch}:{path_to_scratch} {sing} padmet pgdb_to_padmet --source=annot_{annotool} --pgdb={pgdb} --output={output} --extract-gene --no-orphan --padmetRef={path_to_padmet_ref} -v"
                bigprint(command_pgdb2padmet_source)
                os.system(command_pgdb2padmet_source)

def merge_padmet(output_path, annotation, genomes_names, options, df_summary) : 
    """
    Merge padmets of a same strain all together in one padmet file
    Inputs : 
        output_path (str) : path to Prolipipe's output 
        annotation (list) : names of annotation tools used
        genomes_names (list) : list of genomes names to iterate on
        options (parser) : arguments from parser
    """
    path_to_scratch = options.ptsc
    path_to_singularity = options.ptsi
    padmet_output = os.path.join(output_path, 'padmet')
    output_merged = os.path.join(output_path, 'merged_padmet')
    mkdir(output_merged)

    merged = {}
    for name in genomes_names :  
        if missing_or_empty(os.path.join(output_merged, name + ".padmet")):
            ## Check if 3 files are present for merging
            nb_of_padmets=len(os.listdir(os.path.join(padmet_output, name)))
            if nb_of_padmets == len(annotation) :
                to_add = os.path.join(padmet_output, name)
                output = os.path.join(output_merged, name + ".padmet")
                ## Merge annotation files for each genomes into one
                command_padmet2padmet = f"singularity run -B {path_to_scratch}:{path_to_scratch} {path_to_scratch}{path_to_singularity} padmet padmet_to_padmet --to_add={to_add}/ --output={output} -v"
                bigprint(command_padmet2padmet)
                os.system(command_padmet2padmet)
            else :
                raise ValueError(f"ERROR : {nb_of_padmets} padmets files for {len(annotation)} in {padmet_output}/{name}, couldn't merge padmets")
        
        if not missing_or_empty(os.path.join(output_merged, name + ".padmet")):
            merged[name] = "OK"
    
    df_summary[f"merged_padmet"] = df_summary["genome"].map(merged)
    return df_summary


def check_files(step, output_path, df_summary, annotation) :
    """
        Check presence of output files after a given step of the workflow ; 
        Save progression in a summary tsv file, identify processable files
        for downstream analysis.
    """
    summary_file = os.path.join(output_path, "metabolic_rec_summary.tsv") 
    
    ## simply save summary file and exit 
    if step == "merge" : 
        df_summary.to_csv(summary_file, sep = "\t", index = False) 
        processed_strains = len(df_summary[df_summary['merged_padmet'] == 'OK'])
        print(f"\nWorkflow is over, {processed_strains}/{len(df_summary)} genomes are completely processed.\n")
        print(f"Please check {summary_file} for more detailed results on file presence :\n{df_summary}")
        return 
    
    ## name "{step}_{annotool}" columns for summary after checking files
    if step == "mpwt" :
        path = os.path.join(output_path, "mpwt")
        df_summary = check_mpwt(df_summary, path)
    elif step == "padmet" :
        path = os.path.join(output_path, "padmet")
        df_summary = check_padmet(df_summary, path)  
    list_step = [f"{step}_{annotool}" for annotool in annotation]

    ## name "annotool" columns for summary ; files already checked
    if step == "annot" :
        list_step = annotation
    
    ## add the columns and save summary
    df_summary[f'overall_{step}'] = np.where(df_summary[list_step].eq('OK').all(axis=1), 'yes', 'no')
    df_summary.to_csv(summary_file, sep = "\t", index = False)  

    ## define processable genomes for downstream analyses
    df_consensus = df_summary[df_summary[f"overall_{step}"] == "yes"]
    genomes_names = df_consensus["genome"]  

    return df_summary, genomes_names

def rename(file) : 
    """
        Rename file by converting error-generating characters into "-" 
    """
    for old, new in {'.': '-', ':': '-', '__': '-', '-_': '-'}.items():
        file = file.replace(old, new)
    return file

def check_taxfile(options) :
    taxfile = options.taxfile
    genomes = options.input
    if not os.path.exists(taxfile) : 
        return False, f"ERROR : no file found at {taxfile}"
    try :
        df_taxa = pd.read_csv(taxfile, sep = "\t")
        cols = df_taxa.columns
        col_filename = cols[2]
    except :
        return False, f"ERROR : Error reading file at the following path ; are you sure it's a tab-separated file ? \n{taxfile}"

    for i, row in df_taxa.iterrows() :
        file = row[col_filename]
        new_filename = rename(file)
        if file != new_filename :
            ## renaming fasta in taxafile
            df_taxa.at[i, col_filename] = new_filename

            ## renaming fasta and its directory
            dir = os.path.join(genomes, file)
            fasta = glob.glob(os.path.join(dir, "*.fasta"))
           
            try :
                # print(f"{fasta[0]}\n\t{os.path.join(dir, f'{new_filename}.fasta')}")
                # print("\n", dir, "\n\t", os.path.join(genomes, new_filename))
                move(fasta[0], os.path.join(dir, f"{new_filename}.fasta"))
                move(dir, os.path.join(genomes, new_filename))
            except : 
                return False, f"ERROR : No fasta (*.fasta) found in {dir}" 
    df_taxa.to_csv(taxfile, sep = "\t", index=False)
    return True, ""


def main() :
    ## parsing arguments 
    options = parser()
    input_dir = options.input
    output_path = options.output

    ## Creating output directory
    mkdir(output_path)    
    annotation = options.annot.split(",") 
    df_summary = pd.DataFrame(columns = ["genome"])

    ## unzipping and renaming to fasta if needed
    check_gzipped_only(input_dir)

    tax_ok, message = check_taxfile(options)
    if not tax_ok : 
        print(message)
        exit(0)

    ## annotation 
    for annotool in annotation : 
        start = time.time()
        if annotool == 'prokka' :
            genomes_processed = prokka_annotation(input_dir, output_path, options)  
        elif annotool == 'eggnog' :
            genomes_processed = eggnog_annotation(input_dir, output_path, options)
        elif annotool == 'bakta' :
            genomes_processed = bakta_annotation(input_dir, output_path, options)
        else :
            continue
        time_taken =  time.time() - start
        print(f"INFO : {annotool} annotation took {time_taken // 3600} hour(s) {(time_taken % 3600) // 60} minute(s) {time_taken % 60} seconds")
        
        df_summary = df_summary.merge(genomes_processed, on = "genome", how = "outer")
    
    ## summarize annotation results and save it
    df_summary = df_summary.sort_values(by="genome", ascending=True)
    df_summary, genomes_names = check_files("annot", output_path, df_summary, annotation)

    ## mpwt's metabolic network construction step 
    create_taxon_file(annotation, genomes_names, options)
    start = time.time()
    run_mpwt(output_path, annotation, genomes_names, options)
    time_taken =  time.time() - start
    print(f"INFO : Mpwt step took {time_taken // 3600} hour(s) {(time_taken % 3600) // 60} minute(s) {time_taken % 60} seconds")
        
    ## checking if mpwt ran correctly for all annotools, identify convertible genomes and convert them using padmet
    df_summary, genomes_names = check_files("mpwt", output_path, df_summary, annotation)
    start = time.time()
    convert2padmet(output_path, annotation, genomes_names, options)
    time_taken =  time.time() - start
    print(f"INFO : Conversion to padmet took {time_taken // 3600} hour(s) {(time_taken % 3600) // 60} minute(s) {time_taken % 60} seconds")
    
    ## checking if padmet ran correctly for all annotools, save progression
    df_summary, genomes_names = check_files("padmet", output_path, df_summary, annotation)
    
    ## identify mergeable genomes
    df_consensus = df_summary[df_summary["overall_annot"] == "yes"]
    genomes_names = df_consensus["genome"]

    ## merge padmets and save summary
    start = time.time()
    df_summary = merge_padmet(output_path, annotation, genomes_names, options, df_summary)
    time_taken =  time.time() - start
    print(f"INFO : Merging padmets step took {time_taken // 3600} hour(s) {(time_taken % 3600) // 60} minute(s) {time_taken % 60} seconds")
    
    check_files("merge", output_path, df_summary, annotation)
    
       

if __name__ == "__main__":
    ## input : /home/genouest/dyliss/norobert/to_scratch/strains/genomes_dl_from_NCBI/genomes_cirm-bia/cirm_downloaded
    ## output : /scratch/norobert/prolific_project/run2
    main()
    # /home/genouest/dyliss/norobert/miniconda3/envs/prolific/bin/python bin/metabolic_reconstruction.py --input /scratch/norobert/strains/genomes_dl_from_NCBI/genomes_cirm-bia/cirm_downloaded/ --tax /scratch/norobert/prolific_project/taxons/taxons_run2_3.tsv --output /scratch/norobert/prolific_project/run2/ --cpus 2 --padmet_ref /scratch/norobert/metacyc_27.0.padmet --ptsc /scratch/norobert/ --ptsi mpwt_27.sif --annot bakta,prokka,eggnog --bak_path /scratch/norobert/dbs/db_bakta/ --egg_path /db/eggnog/5.0.2/
