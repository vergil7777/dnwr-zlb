"""
We have data dictionaries parsed in an HDFStore.
We have the cps zipped repo.

Combine for an HDFStore of CPS tables.

Note on layout:

cps_store/
    monthly/
        dd/
        data/
            mYYYY_MM
            mYYYY_MM

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
import re
import os
import json
import itertools
import subprocess

import pathlib
import pandas as pd
from matplotlib.cbook import flatten


#-----------------------------------------------------------------------------
# File Handling / IO
#-----------------------------------------------------------------------------

class FileHandler(object):
    """
    Takes care of file system details when working on the zipped files.
    Handles .Z, .zip, .gzip.


    Sorry windows; Replace subprocess.call with appropriate utility.
    Implements context manager that decompresses and cleans up once
    the df has been read in.

    Parameters
    ----------

    fname : String, path to zipped file.
    force : Bool, default False.  If True will unzip and rezip the gzip file.

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
        subprocess.call(["gzip", self.compname])  # Gives warnings on zips.
        if self.fname.endswith('.gz') and self.force:
            os.remove(self.fname.replace('.gz', '.txt'))
        if self.fname.endswith('.zip'):
            os.remove(self.new_path)


def writer(df, name, store_path, settings):
    """
    Write the dataframe to the HDFStore. Non-pure.

    Parameters
    ----------
    df: DataFrame to be writter
    name: name in the table; will be prepended with '/monhtly/data/m'
    store_path: path to the store.  Get from settings.

    Returns
    -------
    None - IO
    """
    with pd.get_store(store_path) as store:
        try:
            store.remove('/monthly/data/' + name)
        except KeyError:
            pass
        store.append('/monthly/data/' + name, df)

    with open(settings["store_log"], 'a') as f:
        f.write('PASSED {}\n'.format(name))


#-----------------------------------------------------------------------------
# Duplicate Handling
#-----------------------------------------------------------------------------


def dedup_cols(df):
    """
    Drops columns that are duplicated.  Have to transpose for unknown reason.
    I'm hitting multiple PADDING's, that should be it.

    Parameters
    ----------
    df : DataFrame

    Returns
    df : Same DataFrame, less the dupes.
    """
    idx = df.columns
    dupes = idx.get_duplicates()
    print("Duplicates: {}".format(dupes))
    return df.T.drop(dupes).T


def pre_process(df, ids):
    """
    Get DataFrame ready for writing to store.

    Makes (hopefully) unique index and makes types numeric.

    Parameters
    ----------
    df  : DataFrame
    ids : Columns to be used as the index.

    Returns
    -------
    df : DataFrame
    """
    df = dedup_cols(df)
    # May want to be careful with index here.
    # forcing numeric chops of leading zeros.
    df = df.convert_objects(convert_numeric=True)
    df = df.set_index(ids)
    return df


def drop_invalid_indicies(df, dd_name=None):
    """
    df: Full dataframe
    dd_name: name to lookup
    """
    # Generalize to getting the -1 (invlaid) from settings.
    valids = df[~(df.apply(lambda x: x.name[2] == -1, axis=1))]
    return valids


def drop_duplicates_index(df, dupes=None):
    """Isn't a method on the dataframe oddly"""
    if dupes is None:
        dupes = df.index.get_duplicates()
    return df.ix[~(df.index.isin(dupes))]


def make_regex(style=None):
    if style is None:
        return re.compile(r'(\w{1,2}[\$\-%]\w*|PADDING)\s*CHARACTER\*(\d{3})\s*\.{0,1}\s*\((\d*):(\d*)\).*')
    elif style is 'aug2005':
        return re.compile(r'(\w+)[\s\t]*(\d{1,2})[\s\t]*(.*?)[\s\t]*\(*(\d+)\s*-\s*(\d+)\)*$')
    elif style is 'jan1998':
        return re.compile(r'D (\w+) \s* (\d{1,2}) \s* (\d*)')


def handle_dupes(df, settings):
    """
    Get subset of df that doesn't have duplicated index.

    Parameters
    ----------

    df : DataFrame.  Index should have name
    settings: dict.

    Returns
    -------

    deduped: DataFrame with duplicate indicies removed.
    """
    dupes = df.index.get_duplicates()
    parts = (df.xs(x) for x in dupes)
    deduped = drop_duplicates_index(df, dupes=dupes)

    dupe_file = settings['dupe_path'] + df.index.name + '.csv'

    with open(dupe_file, 'w') as f:
        header = ','.join(map(str, df.index.names) + df.columns.tolist()) + '\n'
        f.write(header)

    for part in parts:
        part.to_csv(dupe_file, mode='a', header=False)

    print("Deduplicated {}".format(df.index.name))
    return deduped


def handle_89_pt1(df):
    """Bad formatting this year"""
    chars = {'$': '_', '%': '__', '&': '___', '-': '____'}
    for key, val in chars.iteritems():
        df.rename(columns=lambda x: x.replace(key, val), inplace=True)
    return df


def handle_89_pt2(df):
    """After numeric.  Get only adult records."""
    df = df[df['H____RECTYP'] == 1]
    return df

#-----------------------------------------------------------------------------
# Helpers
#-----------------------------------------------------------------------------


def get_dd(fname, settings=None):
    """
    Helper to get the data dictionary associated with a given month's filename.

    Parameters
    ----------
    fname: str, either full or shortened should work.
    settings: str or None.  Path to the settings file

    Returns
    -------
    dd: str, name of data dictionary.
    """
    if settings is None:
        settings = json.load(open('settings.txt'))
    just_name = fname.split('/')[-1].split('.')[0]
    return settings['month_to_dd_by_filename'][just_name]


def get_id(target, store):
    """
    Target is a str, e.g. HHID; This finds all this little
    idiosyncracies.
    """
    for key in store.keys():
        dd = store.select(key)
        yield key, dd.id[dd.id.str.contains(target)]


def get_definition(code, dd_path=None, style=None):
    """
    Get the definition for a code.

    Maybe add option to pass dd_name with a lookup from settings as convinence.
    """

    regex = make_regex(style)

    def dropper(line):
        maybe_match = regex.match(line)
        try:
            line_code = maybe_match.groups()[0]
            return line_code
        except AttributeError:
            return None

    def get_def(dd):
        """
        Next of dd is the line you start with.  Now consume up to next match.
        """
        top_line = [''.join(list(next(dd)))]
        rest = it.takewhile(lambda x: regex.match(x) is None, dd)
        rest = [''.join(x) for x in rest]
        top_line.append(rest)
        return top_line

    with open(dd_path) as dd:
        gen = it.dropwhile(lambda x: dropper(x) != code, dd)
        definition = get_def(gen)
        return definition


def grouper(dict_, ):
    """
    Another helper for checking the fields.

    Parameters
    ----------

    dict_: dictionary

    Returns
    -------
    matched : list
    remainder : list
    """
    # Convert dict to sorted list of items
    list_ = sorted(dict_.items(), key=lambda x: x[1])

    # Group by value of tuple
    groups = itertools.groupby(list_, key=lambda x: x[1])

    # Pull out matching groups of items, and combine items
    # with no matches back into a single dictionary

    dict_groups = {key: list(group) for key, group in groups}
    trues = [x[0] for x in dict_groups[True]]
    falses = [x[0] for x in dict_groups[False]]
    return {True: trues, False: falses}


def check_fieldname(field, settings, dd=None, store_path=None):
    """
    Helper to see if a given field is in a data dictionary.

    Parameters
    ----------

    field : str or list.  Column in df or row in dd.id.
    settings : JSON settings file.
    dd : DataFrame.  With col containing fields.
    store_path : path within store to dd. Only used if dd is None.

    Returns
    -------

    grouped : dict of True : [], False: []

    Example
    -------

    >>> check_fieldname(flatten(settings['dd_to_vars']['may2012'].values()),
                        settings, dd=dd)

    """
    if dd is None:
        with pd.get_store(settings['store_path']) as store:
            dd = store.select(store_path)

    if isinstance(field, str):
        fields = [field]
    else:
        fields = list(field)

    ungrouped = {x: x in dd.id.values for x in fields}
    grouped = grouper(ungrouped)
    return grouped


def find_attr(attr, fields=None, dd=None, settings=None):
    """
    Dictionary may lie.  Check here.

    Parameters
    ----------
    attr: str; e.g. "AGE", "RACE", "SEX"
    fields: array-like; probably columns of the dataframe.
    dd : str or DataFrame; path inside the store or the DD itself.
    settings: dict with "store_path"
    Returns
    -------

    List of strs possible matches.
    """
    if settings is None:
        settings = json.load(open('settings.txt'))

    store = pd.HDFStore(settings["store_path"])

    if fields is not None and dd is not None:
        raise ValueError('One of fields and dd must be specified.')
    elif fields is None and dd is None:
        raise ValueError('One of fields and dd must be specified.')
    elif dd and isinstance(dd, str):
        dd = store.select(dd)
        fields = dd.id.tolist()
    elif dd and isinstance(dd, pd.DataFrame):
        fields = dd.id.tolist()

    store.close()

    match_with = re.compile(r'[\w|$%\-]*' + attr + r'[\w|$%\-]*')
    maybe_matches = (match_with.match(x) for x in fields)
    return [x.string for x in filter(None, maybe_matches)]


def run_one(path, settings, n=10):
    """
    Helper to get a single month's data and data dictonary.

    Parameters
    ----------

    path : str. path to the raw data.
    settings : dict. From the settings JSON file.
    n : int.  Number of rows to read.  None if you want it all.

    Returns
    -------

    df, dd : tuple with DataFrame and Data Dictonary.
    """
    dds = pd.HDFStore(settings['store_path'])
    month = pathlib.Path(path)
    just_name, out_name, s_month, name, dd_name = name_handling(month, settings)

    ids = settings["dd_to_ids"][dd_name]
    dd = dds.select('/monthly/dd/' + dd_name)
    widths = dd.length.tolist()

    if s_month.endswith('.gz'):
        df = pd.read_fwf(name + '.gz', widths=widths,
                         names=dd.id.values, compression='gzip', nrows=n)
    else:
        with FileHandler(s_month) as handler:
            try:
                name = handler.new_path
            except AttributeError:
                pass
            df = pd.read_fwf(name, widths=widths, names=dd.id.values, nrows=n)

    if dd_name in ['jan1989', 'jan1992']:
        df = handle_89_pt1(df)

    df = pre_process(df, ids=ids).sort_index()

    if dd_name in ['jan1989', 'jan1992']:
        df = handle_89_pt2(df)

    # subset = get_subset(df, settings=settings)
    df.index.name = out_name

    return df, dd
#-----------------------------------------------------------------------------
# Logging
#-----------------------------------------------------------------------------


def log_and_store(df):
    with open('ready_to_store.txt', 'w') as f:
        if df.index.is_unique:
            f.write('Ready: {}\n'.format(df.index.name))
        else:
            dupes = df.index.get_duplicates()
            f.write('Dupes: {}\n'.format(df.index.name))
            f.write("\t\t {}".format(dupes))


def get_skips(file_):
    with open(file_, 'r') as f:
        skips = [line.split(' ')[-1].rstrip()
                 for line in f if line.startswith('PASSED')]
    return skips


#-----------------------------------------------------------------------------
# MISC
#-----------------------------------------------------------------------------
def get_subset(df, settings, dd_name, quiet=False):
    """
    Select only those columns specified under settings.
    Optionaly

    Parameters
    ----------

    df : DataFrame
    settings : dictionary with "dd_to_vars" column
    quit: Bool.  If True will print, but not raise, on some columns
    from settings not being in the df's columns.

    Returns
    -------

    subset : DataFrame.
    """
    cols = {x for x in flatten(settings["dd_to_vars"][dd_name].values())}
    subset = df.columns.intersection(cols)

    if not quite:
        print("Implicitly dropping {}".format(cols.symmetric_difference(subset)))

    return df[subset]


def name_handling(month, settings, skip=True):
    """
    Handle all the name stuff for a function run.

    Parameters
    ----------

    month: pathlib.Path object.  Path to the data.
    settings : JSON dictionary.

    Returns
    -------

    just_name : str; filename without any leading directories.
    out_name : str; For use in store.  'm' + iso8601.
    s_month : str; same as month but in str form.
    name : str; month without the file extension.
    dd_name : str; data dictionary name.
    """
    just_name = month.parts[-1].split('.')[0]
    if just_name == '' or month.is_dir():
        return just_name, _, _, _, _

    out_name = 'm' + settings['file_to_iso8601'][just_name]
    s_month = str(month)
    name = s_month.split('.')[0]
    dd_name = settings["month_to_dd_by_filename"][just_name]

    return just_name, out_name, s_month, name, dd_name


def main():
    import sys
    try:
        settings = json.load(open(sys.argv[1]))
    except IndexError:
        settings = json.load(open('settings.txt'))
    #-------------------------------------------------------------------------
    # setup
    raw_path  = pathlib.Path(str(settings['raw_monthly_path']))
    base_path = settings['base_path']
    repo_path = settings['repo_path']
    dds       = pd.HDFStore(settings['store_path'])

    skips = get_skips(settings['store_log'])

    for month in raw_path:
        try:
            just_name, out_name, s_month, name, dd_name = (
                name_handling(month, settings))

            if just_name == '' or month.is_dir():  # . files or subdirs
                continue

            ids = settings["dd_to_ids"][dd_name]

            if out_name in skips and skip:
                continue

            try:
                dd = dds.select('/monthly/dd/' + dd_name)
                widths = dd.length.tolist()
            except KeyError:
                print("No data dictionary for {}".format(out_name))
                continue

            if s_month.endswith('.gz'):
                df = pd.read_fwf(name + '.gz', widths=widths,
                                 names=dd.id.values, compression='gzip')
            else:
                with FileHandler(s_month) as handler:
                    try:
                        name = handler.new_path
                    except AttributeError:
                        pass
                    df = pd.read_fwf(name, widths=widths, names=dd.id.values)

            if dd_name in ['jan1989', 'jan1992']:
                df = handle_89_pt1(df)

            df = pre_process(df, ids=ids).sort_index()

            if dd_name in ['jan1989', 'jan1992']:
                df = handle_89_pt2(df)

            cols = settings['dd_to_vars'][dd_name].values()

            subset = get_subset(df, settings=settings)
            df.index.name = out_name

            #---------------------------------------------------------------------
            # Ensure uniqueness
            if not df.index.is_unique:
                df = handle_dupes(df, settings=settings)
                assert df.index.is_unique
            #---------------------------------------------------------------------
            # Writing
            store_path = settings['store_path']
            writer(df, name=out_name, store_path=store_path, settings=settings)
            print('Added {}'.format(out_name))
        except:
            with open(settings["store_log"], 'a') as f:
                f.write('FAILED {}\n'.format(name))
    pass
#-----------------------------------------------------------------------------
if __name__ == '__main__':
    main()
