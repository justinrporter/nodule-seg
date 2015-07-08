import sys
import argparse
import os

import SimpleITK as sitk  # pylint: disable=F0401


def process_command_line(argv):
    '''Parse the command line and do a first-pass on processing them into a
    format appropriate for the rest of the script.'''

    parser = argparse.ArgumentParser(formatter_class=argparse.
                                     ArgumentDefaultsHelpFormatter)

    parser.add_argument(
        "--dicomdirs", nargs="+",
        help="The dicom directories to operate on.")

    args = parser.parse_args(argv[1:])

    return args


def dicom_files(indir):
    '''Returns a list of the names of all files in a dicom series given the
    directory in which they're stored.'''
    reader = sitk.ImageSeriesReader()
    return reader.GetGDCMSeriesFileNames(indir)


def dicom_hash(dicom):
    '''Compute an the sha1 hash of the contents of a dicom stack. Returns the
    hexadecimal representation as a string.'''
    import hashlib

    sha = hashlib.sha1()

    for dcm in dicom_files(dicom):
        with open(dcm, 'rb') as f:
            sha.update(f.read())

    return sha.hexdigest()


def dicom_to_nii(indir, output):
    '''Convert an input dicom directory to a nii file.'''
    reader = sitk.ImageSeriesReader()
    reader.SetFileNames(dicom_files(indir))

    out = sitk.ImageFileWriter()
    out.SetFileName(output)
    out.Execute(reader.Execute())


def convert_to_nii(dicom_in, nifti_dir):
    '''Convert the given dicom directory (dicom_in) into a nifti formatted
    image and place it in nifti_dir using an md5 hash of its contents.
    Returns the absolute path of the output file'''
    try:
        os.makedirs(nifti_dir)
    except OSError:
        # no need to do anything if the directory already exists.
        pass

    sha = dicom_hash(dicom_in)

    outname = os.path.join(nifti_dir, sha+".nii")
    dicom_to_nii(dicom_in, outname)

    return sha


def main(argv=None):
    '''Run the driver script for this module. This code only runs if we're
    being run as a script. Otherwise, it's silent and just exposes methods.'''
    args = process_command_line(argv)

    print args

    return 1

if __name__ == "__main__":
    sys.exit(main(sys.argv))
