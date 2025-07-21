
MeReco : Large-scale Metabolic Reconstruction from bacterial genomes 
==========================================

Workflow to reconstruct multiple metabolic graphs directly from sequence fasta.

.. contents:: Table of contents
   :backlinks: top
   :local:

License
--------
This workflow is licensed under the GNU GPL-3.0-or-later, see the `LICENSE <https://github.com/AuReMe/mereco/blob/main/LICENSE>`__ file for details.

Installation
------------

Dependencies
~~~~~~~~~~~~

These tools are needed:

	- `Prokka <https://github.com/tseemann/prokka>`__

	- `EggNOG-mapper <https://github.com/eggnogdb/eggnog-mapper>`__

	- `Bakta <https://github.com/oschwengers/bakta>`__

	- `Pathway Tools <http://bioinformatics.ai.sri.com/ptools/>`__ (which needs `Blast <https://blast.ncbi.nlm.nih.gov/Blast.cgi?PAGE_TYPE=BlastDocs&DOC_TYPE=Download>`__)


And some python packages:

	- `mpwt <https://github.com/AuReMe/mpwt>`__

	- `padmet <https://github.com/AuReMe/padmet>`__

	- `pandas <https://pandas.pydata.org/>`__


Installation of Pathway Tools
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To run annotation based reconstruction, you need to install Pathway Tools. This tool is 
available at the `Pathway Tools <http://bioinformatics.ai.sri.com/ptools/>`__ website. 


Getting the MetaCyc PADMET file
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You also should install the MetaCyc_XX.X.padmet (the version number of 
`MetaCyc <https://metacyc.org/>`__  is replaced with XX.X), and then you should update your 
config.txt files for each study. This is the way to get a MetaCyc_XX.padmet file: 
Firstly, download the flat files of `MetaCyc <https://metacyc.org/>`__ in DAT format at the
`https://biocyc.org/download.shtml <https://biocyc.org/download.shtml>`__ webpage. 
Secondly, put all the downloaded DAT files in a directory (it is named FLAT_DIR here). 
Thirdly run this command:

.. code:: sh

	padmet pgdb_to_padmet --pgdb=FLAT_DIR --output=metacyc_XX.X.padmet --version=XX.X --db=Metacyc -v

pip
~~~

If you have installed all the dependencies, you can just install MeReco with:

.. code:: sh

	pip install mereco

Usage
-----

.. code:: python

 metabolic_reconstruction.py [-h] -i INPUT -o OUTPUT --tax TAXFILE --padmet_ref PATH_TO_PADMET_REF --ptsc PTSC --ptsi PTSI [--annot ANNOT] [--egg_path EGG_PATH] [--bak_path BAK_PATH]
                             [-c CPUS] [-k TO_KEEP] [-q]

-k flag can be used to save some intermediary files from Prokka and Bakta (listed blow). 
To keep some specific files, mention their extension separated by ",", following the structure below : 
	Prokka : .ecn,.err,.ffn,.fixed*,.fsa,.gff,.log,.sqn,.tbl,.val,.faa
	Bakta : .embl,.faa,.ffn,.fna,.gff3,.hypotheticals.faa,.hypotheticals.tsv,.json,.log,.png,.svg,.tsv