"""
We have data dictionaries parsed in an HDFStore.
We have the cps zipped repo.

Combine for an HDFStore of CPS tables.

Note on layout:

cps_store/
    monthly/
        dd/
        data/
            jan1989
            feb1989

Want to keep pythonic names so I can't go 2013-01.

See generic_data_dictionary_parser.Parser.get_store_name for info
on which year gets which dd.

They claim to use
    (HHID, HHNUM, LINENO)
for '94 that is "HRHHID", "HUHHNUM", "PULINENO"
and validate with
    sex, age, race


Possiblye interested in

    PTERNH1C-Earnings-hourly pay rate,excluding overtime
    PTERNH2-T Earnings-(main job)hourly pay rate,amount
**  PTWK-T Earnings-weekly-top code flag  **

"""
import os
import json
import subprocess

import pathlib
import pandas as pd


def tst_setup(n=10):
    settings = json.load(open('info.txt'))
    dds = pd.HDFStore(settings['store_path'])
    base_path = settings['base_path']
    repo_path = settings['repo_path']
    dd = dds.select('/monthly/dd/jan1998')
    pth = '/Volumes/HDD/Users/tom/DataStorage/CPS/monthly/cpsb9810.gz'
    widths = dd.length.tolist()
    df = pd.read_fwf(pth, widths=widths, nrows=n, names=dd.id.values, compression='gzip')
    return df, dd, dds


def runner(fname, n=10, settings=json.load(open('info.txt'))):
    dds = pd.HDFStore(settings['store_path'])
    no_ext = ''.join(fname.split('.')[:-1])
    dd_month = settings['month_to_dd_by_filename'][no_ext.split('/')[-1] + '.Z']
    dd = dds.select('/monthly/dd/' + dd_month)
    widths = dd.length.tolist()
    if fname.endswith('.Z'): 
        pth = ''.join(fname.split('.')[:-1])
        df = pd.read_fwf(pth, widths=widths, nrows=n, names=dd.id.values)
    elif fname.endswith('.gz'):
        df = pd.read_fwf(fname, widths=widths, nrows=n, names=dd.id.values,
                         compression='gzip')
    else:
        raise IOError('Was the thing even zipped?')
    return df, dd


def dedup_cols(df):
    """
    Will append a suffix to the index keys which are duplicated.

    I'm hitting multiple PADDING's.
    """
    idx = df.columns
    dupes = idx.get_duplicates()
    print("Duplicates: {}".format(dupes))

    return df.T.drop(dupes).T


def pre_process(df, ids):
    df = dedup_cols(df)
    # May want to be careful with index here.
    # forcing numeric chops of leading zeros.
    df = df.convert_objects(convert_numeric=True)
    df = df.set_index(ids)
    return df


class FileHandler(object):
    """
    Just useful the first time since I'm rezipping as gzip, which can be parsed
    on the fly.

    Sorry windows; Replace subprocess.call with appropriate utility.
    Implements context manager that decompresses and cleans up once
    the df has been read in.

    Example:
        fname = 'Volumes/HDD/Users/tom/DataStorage/CPS/monthly/cpsb0201.Z'
        with file_handler(fname):
            pre_process(df)


    """
    def __init__(self, fname, force=False):
        if os.path.exists(fname):
            self.fname = fname
            self.force = force
        else:
            raise IOError("The File does not exist.")

    def __enter__(self):

        if self.fname.endswith('.Z'):
            subprocess.call(["uncompress", "-v", self.fname])
        elif self.fname.endswith('.gzip'):
            if self.force:
                subprocess.call(["gzip", "-d", self.fname])
            else:
                print('Skipping decompression.')
        elif self.fname.endswith('.zip'):
            dir_name = '/'.join(self.fname.split('/')[:-1])
            # Unzipping gives new name; can't control.  Get diff
            current = {x for x in pathlib.Path(dir_name)}
            subprocess.call(["unzip", self.fname, "-d", dir_name])
            new = ({x for x in pathlib.Path(dir_name)} - current).pop()
            self.new_path = str(new)
        self.compname = self.fname.split('.')[0]
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        subprocess.call(["gzip", self.compname])
        if self.fname.endswith('.gz') and self.force:
            os.remove(self.fname.replace('.gz', '.txt'))
        if self.fname.endswith('.zip'):
            os.remove(self.new_path)

def get_id(target, store):
    """
    Target is a str, e.g. HHID; This finds all this little
    idiosyncracies.
    """
    for key in store.keys():
        dd = store.select(key)
        yield key, dd.id[dd.id.str.contains(target)]


if __name__ == '__main__':
    import sys

    try:
        settings = json.load(open(sys.argv[1]))
    except IndexError:
        settings = json.load(open('info.txt'))

    raw_path  = pathlib.Path(str(settings['raw_monthly_path']))
    base_path = settings['base_path']
    repo_path = settings['repo_path']
    dds       = pd.HDFStore(settings['store_path'])

    for month in raw_path:
        try:
            s_month = str(month)
            name = s_month.split('.')[:-1]
            just_name = month.parts[-1].split('.')[0]
            dd_name = settings["month_to_dd_by_filename"][just_name]
            ids = settings["dd_to_ids"][dd_name]
            dd = dds.select('/monthly/dd/' + dd_name)
            widths = dd.length.tolist()
            if s_month.endswith('.gz'):
                df = pd.read_fwf(name + '.gz', widths=widths,
                                 names=dd.id.values, compression='gzip')
            else:
                with FileHandler(s_month) as handler:
                    import ipdb; ipdb.set_trace()
                    try:
                        name = handler.new_path
                    except AttributeError:
                        pass
                    df = pd.read_fwf(name, widths=widths, names=dd.id.values,
                                     nrows=10)
            df = pre_process(df, ids=ids)
        except KeyError:
            print(month)
