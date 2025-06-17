# koreader-to-sioyek

A python script to import highlights made in [KOReader](https://github.com/koreader/koreader) into the [Sioyek](https://github.com/ahrm/sioyek) PDF viewer.

The script will maintain original highlight color and only add new highlights.

The alpha script is compatible with Sioyek's latest alpha release and will import both highlights and comments.

## Usage

- set the path to Sioyek and its database files in the script
- run with `koreader-to-sioyek.py <directory>` where directory contains the PDFs and their respective metadata.pdf.lua files
- to run without arguments, set KOREADER_DIRECTORY to the directory in the script
