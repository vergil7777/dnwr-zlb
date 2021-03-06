from datetime import datetime
import itertools as it

import arrow
import numpy as np
import pandas as pd
import statsmodels.api as sm


def sane_names(df):
    names = _gen_items()
    if isinstance(df, pd.Panel):
        return df.rename(items=names, minor_axis=names)
    return df.rename(columns=names)


def _gen_items():
    """
    Keep one dict of interesting items. Filter this down.
    """
    d = {'PRTAGE': 'age',
         'PRERNWA': 'earnings',
         'PEEDUCA': 'edu',
         'PEHRUSL1': 'hours',
         'PEMLR': 'labor_status',
         'PEMARITL': 'married',
         'HRMONTH': 'month',
         'PTDTRACE': 'race',
         'PESEX': 'sex',
         'HRYEAR4': 'year',
         'PUIODP1': 'same_employer',
         'flow': 'flow',
         'timestamp': 'timestamp',
         'unemployed_history': 'unemployed_history',
         'nonemployed_history': 'nonemployed_history',
         'either_history': 'either_history',
         'HRMIS': 'month_in_sample',
         'PRDTIND1': 'industry',
         'PRDTOCC1': 'occupation',
         'PEHRACT1': 'actual_hours',
         "PWORWGT": "og_weight"}
    # TODO: check on older industries/occupation codes.
    return d


def get_useful(df, strict=True):
    df = sane_names(df)
    # TODO: grab cols from convert_names.keys()
    # or both from a common function.
    cols = _gen_items().values()
    no_history = list(set(cols) - {'unemployed_history', 'nonemployed_history',
                                   'either_history', 'flow'})
    if isinstance(df, pd.Panel):
        try:
            res = df.loc[cols]
        except KeyError:
            if strict:
                raise KeyError("Missing {}".format(set(df.columns) - set(cols)))
            else:
                res = df.loc[no_history]
    else:
        try:
            res = df[cols]
        except KeyError:
            if strict:
                raise KeyError("Missing {}".format(set(df.columns) - set(cols)))
            else:
                res = df[no_history]
    return res


def replace_categorical(df, kind=None, inverse=False, index=None,
                        columns=None):
    """
    Replace the numeric values with catigorical for a DataFrame.

    kind must be one of {'sex', 'race', 'married', 'labor_status', 'industry',
        'occupation', 'edu'}
    by defualt all are replaced.
    """
    sex = {1: "male", 2: "female"}
    race = {1: "White Only",
            2: "Black Only",
            3: "American Indian, Alaskan Native Only",
            4: "Asian Only",
            5: "Hawaiian/Pacific Islander Only",
            6: "White-Black",
            7: "White-AI",
            8: "White-Asian",
            9: "White-HP",
            10: "Black-AI",
            11: "Black-Asian",
            12: "Black-HP",
            13: "AI-Asian",
            14: "AI-HP",
            15: "Asian-HP",
            16: "W-B-AI",
            17: "W-B-A",
            18: "W-B-HP",
            19: "W-AI-A",
            20: "W-AI-HP",
            21: "W-A-HP",
            22: "B-AI-A",
            23: "W-B-AI-A",
            24: "W-AI-A-HP",
            25: "Other 3 Race Combinations",
            26: "Other 4 and 5 Race Combinations"}
    married = {1: "MARRIED, CIVILIAN SPOUSE PRESENT",
               2: "MARRIED, ARMED FORCES SPOUSE PRESENT",
               3: "MARRIED, SPOUSE ABSENT (EXC. SEPARATED)",
               4: "WIDOWED",
               5: "DIVORCED",
               6: "SEPARATED",
               7: "NEVER MARRIED"}
    # 1 & 2 is employed
    # 3 & 4 is unemployed
    # 1 - 4 is labor force
    labor_status = {1: "employed",
                    2: "absent",
                    3: "layoff",
                    4: "looking",
                    5: "retired",
                    6: "disabled",
                    7: "other"}

    industry = {1: "Agriculture",
                2: "Forestry, logging, fishing, hunting, and trapping",
                3: "Mining",
                4: "Construction",
                5: "Nonmetallic mineral product manufacturing",
                6: "Primary metals and fabricated metal products",
                7: "Machinery  manufacturing",
                8: "Computer and electronic product manufacturing",
                9: "Electrical equipment, appliance manufacturing",
                10: "Transportation equipment manufacturing",
                11: "Wood products",
                12: "Furniture and fixtures manufacturing",
                13: "Miscellaneous and not specified manufacturing",
                14: "Food manufacturing",
                15: "Beverage and tobacco products",
                16: "Textile, apparel, and leather manufacturing",
                17: "Paper and printing",
                18: "Petroleum and coal products manufacturing",
                19: "Chemical manufacturing",
                20: "Plastics and rubber products",
                21: "Wholesale trade",
                22: "Retail trade",
                23: "Transportation and warehousing",
                24: "Utilities",
                25: "Publishing industries (except internet)",
                26: "Motion picture and sound recording industries",
                27: "Broadcasting (except internet)",
                28: "Internet publishing and broadcasting",
                29: "Telecommunications",
                30: "Internet service providers and data processing services",
                31: "Other information services",
                32: "Finance",
                33: "Insurance",
                34: "Real estate",
                35: "Rental and leasing services",
                36: "Professional and  technical services",
                37: "Management of companies and enterprises",
                38: "Administrative and support services",
                39: "Waste management and remediation services",
                40: "Educational services",
                41: "Hospitals",
                42: "Health care services, except hospitals",
                43: "Social assistance",
                44: "Arts, entertainment, and recreation",
                45: "Accommodation",
                46: "Food services and drinking places",
                47: "Repair and maintenance",
                48: "Personal and laundry services",
                49: "Membership associations and organizations",
                50: "Private households",
                51: "Public administration",
                52: "Armed forces"}

    occupation = {1: "Management",
                  2: "Business and financial operations",
                  3: "Computer and mathematical science",
                  4: "Architecture and engineering",
                  5: "Life, physical, and social science",
                  6: "Community and social service",
                  7: "Legal",
                  8: "Education, training, and library",
                  9: "Arts, design, entertainment, sports, and media",
                  10: "Healthcare practitioner and technical",
                  11: "Healthcare support",
                  12: "Protective service",
                  13: "Food preparation and serving related",
                  14: "Building and grounds cleaning and maintenance",
                  15: "Personal care and service",
                  16: "Sales and related",
                  17: "Office and administrative support",
                  18: "Farming, fishing, and forestry",
                  19: "Construction and extraction",
                  20: "Installation, maintenance, and repair",
                  21: "Production",
                  22: "Transportation and material moving",
                  23: "Armed Forces"}

    edu = {31: "LESS THAN 1ST GRADE",
           32: "1ST, 2ND, 3RD OR 4TH GRADE",
           33: "5TH OR 6TH GRADE",
           34: "7TH OR 8TH GRADE",
           35: "9TH GRADE",
           36: "10TH GRADE",
           37: "11TH GRADE",
           38: "12TH GRADE NO DIPLOMA",
           39: "HIGH SCHOOL GRAD-DIPLOMA OR EQUIV (GED)",
           40: "SOME COLLEGE BUT NO DEGREE",
           41: "ASSOCIATE DEGREE-OCCUPATIONAL/VOCATIONAL",
           42: "ASSOCIATE DEGREE-ACADEMIC PROGRAM",
           43: "BACHELOR'S DEGREE (EX: BA, AB, BS)",
           44: "MASTER'S DEGREE (EX: MA, MS, MEng, MEd, MSW)",
           45: "PROFESSIONAL SCHOOL DEG (EX: MD, DDS, DVM)",
           46: "DOCTORATE DEGREE (EX: PhD, EdD)"}

    flow = {1: 'ee', 2: 'eu', 3: 'en',
            4: 'ue', 5: 'uu', 6: 'un',
            7: 'ne', 8: 'nu', 9: 'nn'}

    history = {-1: 'NaN', 0: 'employed', 1: 'not_employed'}
    replacer = {"sex": sex, "race": race, "married": married,
                "labor_status": labor_status, "industry": industry,
                "occupation": occupation, 'edu': edu, 'flow': flow,
                "history": history}
    if inverse:
        for d in replacer.keys():
            replacer[d] = {v: k for k, v in replacer[d].iteritems()}

    # df.replace(replacer)  # should work. bug

    if index is None and columns is None:
        if kind is None:
            for k, v in replacer.iteritems():
                df[k] = df[k].replace(v)
        else:
            df[kind] = df[kind].replace(replacer[kind])
    elif index is not None:
        df = df.rename(index=replacer[kind])
    elif columns is not None:
        df = df.rename(columns=replacer[kind])
    return df


def edu_to_years(s):
    """
    Replaces education values with approximate years of school.
    """
    d = {31: 1,
         32: 4,
         33: 6,
         34: 8,
         35: 9,
         36: 10,
         37: 11,
         38: 12,
         39: 12,
         40: 14,
         41: 14,
         42: 14,
         43: 18,
         44: 20,
         45: 22,
         46: 22}
    return s.replace(d)


def add_flows(s1, s2, categorical=True):
    """
    take a 2 column dataframe.

    returns a series or str/nan indexed like the 2.
    """
    # 1 & 2 is employed
    # 3 & 4 is unemployed
    # 1 - 4 is labor force
    if categorical:
        c1 = ['employed', 'absent']
        c2 = ['layoff', 'looking']
        c3 = ['retired', 'disabled', 'other']
    else:
        c1 = [1, 2]
        c2 = [3, 4]
        c3 = [4, 5, 6]

    ee = s1.isin(c1) & s2.isin(c1)
    eu = s1.isin(c1) & s2.isin(c2)
    en = s1.isin(c1) & s2.isin(c3)
    ue = s1.isin(c2) & s2.isin(c1)
    uu = s1.isin(c2) & s2.isin(c2)
    un = s1.isin(c2) & s2.isin(c3)
    ne = s1.isin(c3) & s2.isin(c1)
    nu = s1.isin(c3) & s2.isin(c2)
    nn = s1.isin(c3) & s2.isin(c3)

    flows = {"ee": ee, "eu": eu, "en": en, "ue": ue, "uu": uu, "un": un,
             "ne": ne, "nu": nu, "nn": nn}

    s = pd.Series(np.nan, index=s1.index)
    for k, v in flows.iteritems():
        s.loc[v] = k
    return s


def transform_date(month, to='earn'):
    """
    give month and transform to either:
        - the resulting earning (if to=`earn`)
        - the generating panel (if to=`panel`)
    """
    month = month.strip('/').strip('m')
    ar = arrow.get(month, 'YYYY_MM')
    if to == 'earn':
        out = ar.replace(months=15)
    elif to == 'panel':
        out = ar.replace(months=-15)
    else:
        raise ValueError
    return out.strftime('%Y_%m')


def panel_to_frame(wp):
    df = wp.transpose(1, 0, 2).to_frame(filter_observations=False).T.stack().reset_index().set_index(
        ['minor', 'HRHHID', 'HUHHNUM', 'PULINENO']).sort_index()
    return df


def quantile_list(df, quantiles):
    # this will work for both Series and DataFrames
    return type(df)({q: df.quantile(q) for q in quantiles})


def panel_select(store, month):
    # cols = _gen_items().values
    pass


def get_from_earn(month, earn_store, stat='median'):
    df = get_useful(earn_store.select('m' + month))
    df = replace_categorical(df)
    x = df['earnings'].unstack()
    return getattr((x[8] - x[4]), 'median')()


def get_earn_quantiles(month, earn_store, quantiles=[.05, .1, .25, .5, .75, .9, .95]):
    df = get_useful(earn_store.select('m' + month))
    df = replace_categorical(df)
    x = df['earnings'].unstack()
    diff = x[8] - x[4]
    return quantile_list(diff, quantiles)


def get_earn_summary(month, earn_store):
    df = get_useful(earn_store.select('m' + month))
    df = replace_categorical(df)
    x = df['earnings'].unstack()
    diff = x[8] - x[4]
    return diff.describe()


def get_earn_summary_group(month, earn_store):
    df = get_useful(earn_store.select('m' + month))
    df = replace_categorical(df)
    e = df['earnings'].unstack()
    status = df['labor_status'].unstack()
    flows = add_flows(status[4], status[8])
    res = e.groupby(flows).describe()
    return res


def get_earn_diff_with_flow(month, earn_store):
    df = get_useful(earn_store.select('m' + month))
    e = df.earnings.unstack()
    ls = df.labor_status.unstack()
    s1, s2 = ls[4], ls[8]
    e['flow'] = add_flows(s1, s2, categorical=False)
    return e


def make_MultiIndex_date(df, month):
    """"
    You have a dict of {month: dfs} and want to join them. But you need to
    add the date to the existing df's multiIndex.
    """
    df['timestamp'] = pd.to_datetime(month, format='%Y_%m')
    df = df.reset_index()
    df = df.rename(columns={'HUHHNUM': 'HRHHID2'})
    df = df.set_index(['timestamp'] + ['HRHHID', 'HRHHID2', 'PULINENO'])
    return df


def bin_others(ser, others, name="other", strict=True, inplace=False):
    """
    Group together other values before handing off to a groupby.

    Parameters
    ----------

    ser : Series
    others : list
        column names that you want binned into "other"
    how : str
        how to aggregate the other functions. One of {"sum"}
    name : str
        name to give to new bin. Deafult "other"

    Returns
    -------

    Series
    """
    if not inplace:
        ser = ser.copy()

    extras = set(others) - set(ser.unique())
    if extras and strict:
        raise ValueError("others must be a subset of `ser`"
                         " Extra are {}".format(extras))

    ser[ser.isin(others)] = name
    return ser


def df_unique(df, index=None):
    df = [df[x].unique() for x in df]
    assert [len(x) == 1 for x in df]
    ser = pd.Series([x[0] for x in df], index=index)
    return ser


def date_parser(date):
    """

    """
    if '_' in (date):
        # YYYY_MM or /mYYYY_mm
        r = arrow.get(date.lstrip('/').lstrip('m'), 'YYYY_MM')
    elif '-' in (date):
        # YYYY-MM
        r = arrow.get(date, 'YYYY-MM')
    else:
        r = arrow.get(pd.datetools.parse(date))
    return r


def filter_panel(wp, *args):
    """
    Filter on all arguments.

    TODO: criteria should be passable.
    age:
        Those within [25, 60]
    sex:
        Just 1
    """
    filters = {'age', 'sex'}

    if any([x not in filters for x in args]):
        unexpected = set(args) - filters
        raise ValueError(unexpected)

    MONTH = 4
    if MONTH not in wp.loc['age'].columns:
        MONTH = 1

    idxes = []
    if 'age' in args:
        ages = wp.loc['age'][MONTH]
        idxes.append(ages[(ages >= 25) & (ages <= 60)].index)

    if 'sex' in args:
        sex = wp.loc['sex'][MONTH]
        idxes.append(sex[sex == 1].index)

    final_idx = reduce(lambda x, y: x.intersection(y), idxes)

    return wp.loc[:, final_idx]


def _make_timestamps(wp):
    years = wp['year'].dropna()
    months = wp['month'].dropna()

    if isinstance(wp, (pd.DataFrame, pd.Series)):
        years = int(years[0])
        months = int(months[0])
        expected = pd.to_datetime(str(years) + '-' + str(months) + '-01')

    else:
        ncols = len(years.columns)
        idx = range(1, ncols + 1)

        years = df_unique(years, index=idx)
        months = df_unique(months, index=idx)

        expected = pd.to_datetime(years.astype(int).astype(str) + '-' +
                                  months.astype(int).astype(str) + '-01')

    return expected


def chunk_quarters(months, n):
    """
    Chunklist is nice and generic. This deals with stripping the first couple
    that may not have a full quarter and then hands things off the chunklist.

    I wonder if I could use a coroutine?
    """
    a0 = date_parser(months[0])
    months_to_strip = 1 - (a0.month % n)

    yield months[:months_to_strip]
    for x in chunk_list(months[months_to_strip:], n):
        yield x


def chunk_list(l, n):
    """ Yield successive n-sized chunks from l.
    """
    for i in range(0, len(l), n):
        yield l[i:i+n]


def make_chunk_name(chunk, id_='long'):
    """
    Base off first name. Write into quarters.
    """
    m = chunk[0]
    year = m[:4]
    month = int(m[-2:])
    name = id_ + '_' + year + '_Q' + str(int(np.ceil(month / 3.)))
    return name


def select_data(month, panel_store):
    """
    Each panel maps to 8 months. 1 month gathers data from 8 panels.

    if month = 0 then month selects from
        ms = [0, -1, -2, -3, -12, -13, -14, -15]
              ^               ^                 earnings
    """
    a0 = date_parser(month)
    shifters = [0, -1, -2, -3, -12, -13, -14, -15]
    months = [(i, a0.replace(months=x).strftime('%Y_%m')) for i, x
              in enumerate(shifters, 1)]
    for i, m in months:
        try:
            df = filter_panel(get_useful(panel_store.select('m' + m)), 'age')
            df = df.loc[:, :, i]
            yield df
        except KeyError:
            yield None


def read_to_long(store, months):
    """
    Grab all the specified values for every month in a range.

    Parameters
    ----------

    store : pd.HDFStore or filepath
    columns : arraylike
        should be in useful form
    start : YYYY_MM
    stop : YYYY_MM


    Returns
    -------

    Panel4D?
    """

    by_time = []
    for month in months:

        frames = select_data(month, store)
        frames = (df for df in frames if df is not None)
        for df in frames:
            df = df.drop('timestamp', axis=1)
            stamp = _make_timestamps(df)
            df['stamp'] = stamp
            df = df.set_index('stamp', append=True)
            # TODO: submit PR for reorder_levels docstring taking names
            df = df.reorder_levels(['stamp', 'HRHHID', 'HRHHID2', 'PULINENO']).sort_index()
            by_time.append(df)

    df = pd.concat(by_time).sort_index()

    # Transformations
    #--------------------------------------------------------------------------
    # edu bug
    df = fix_edu_bug(df)

    # Add an experience column: Age - years of school - 6
    s = edu_to_years(df['edu'])
    df['expr'] = df['age'] - s - 6

    # replace variable hours (-4) with actual hours
    df = replace_variable_hours(df)
    #--------------------------------------------------------------------------
    return df


def fix_edu_bug(df, inplace=True):
    """read_fwf bug on edu for 2007+; see note.md"""
    edu = df.edu
    edu[edu > 100] = edu[edu > 100].astype('str').str.slice(0, 2).astype(int)
    df['edu'] = edu
    return df


def replace_variable_hours(df, inplace=True):
    """Variable is -4; replace with actual from last week"""
    if not inplace:
        df = df.copy()
    idx = df[df['hours'] == -4].index
    df.loc[idx, 'hours'] = df.loc[idx, 'actual_hours']
    return df


def make_demo_dummies(df):
    """
    Add dummies for
        race : black (2, 6, 10, 11, 12) = 1 (TODO: add hispanic)
        sex  : female (2) = 1
        married : married with spouse present (1, 2) = 1
    """
    race_d = pd.Series(np.zeros(df.shape[0]), index=df.index, name='race_d')
    race_d[df['race'].isin([2, 6, 10, 11, 12])] = 1

    sex_d = pd.Series(np.zeros(df.shape[0]), index=df.index, name='sex_d')
    sex_d[df['sex'] == 2] = 1

    married_d = pd.Series(np.zeros(df.shape[0]), index=df.index,
                          name='married_d')
    married_d[df['married'].isin([1, 2])] = 1

    res = pd.concat([race_d, sex_d, married_d], axis=1)
    res = res.astype(int)
    return res


def bin_education(df):
    """
    Break education into:

        0. Didn't finish highschool (31, 32, 33, 34, 35, 36, 37, 38) < check
        1. Highschool or GED (39)
        2. Some college (40)
        3. Associate (41, 42)
        4. Finished college (43)
        5. Some graduate (44, 45, 46)
    """
    res = pd.Series(np.zeros(df.shape[0]), name='edu_bin')
    res.index = df.index
    edu = df['edu']
    res[edu == 39] = 1
    res[edu == 40] = 2
    res[edu.isin([41, 42])] = 3
    res[edu == 43] = 4
    res[edu.isin([44, 45, 46])] = 5
    res = res.astype(int)
    return res


def add_demo_dummies(df, inplace=True):
    """wrapper for make_demo_dummies and bin_education"""
    if not inplace:
        df = df.copy()

    df = pd.concat([df, make_demo_dummies(df)], axis=1)
    df.loc[:, 'edu_bin'] = bin_education(df)

    return df


def construct_wage_index(df):
    """
    Once you have the cleaned earnings frame, go here.
    Adds in dummies for demographics, bins education.
    """
    model = sm.OLS.from_formula("np.log(real_hr_earns) ~ age + sex_d + race_d +"
                                "married_d + edu_bin + expr + expr**2 +"
                                "expr**3 + expr**4", df)
    res = model.fit()
    return model, res


def make_df_ss(df_fs, params, lrprod, history='either_history'):
    """
    Construct the second stage Dataframe.


    Parameters
    ----------

    df_fs : DataFrame
        should contain all parameter columns, history, and qmonth index
    params : Series
        params series from first stage Results
    lrprod : Series
        log real productivity measure
    history : str
        History to group on. Default `'either_history'`

    Returns
    -------



    """
    g_ts = df_fs.reset_index().groupby(['qmonth', history])
    g_ts_all = df_fs.groupby(level='qmonth')

    parameters = params.index[1:]  # Don't need intercept

    demo_means_ts = g_ts[parameters].mean()
    demo_means_ts_all = g_ts_all[parameters].mean()

    idx = pd.MultiIndex.from_tuples(zip(demo_means_ts_all.index,
                                        it.cycle(['all_'])),
                                    names=demo_means_ts.index.names)
    demo_means_ts_all.index = idx
    demo_means_ts = pd.concat([demo_means_ts, demo_means_ts_all]).sort_index()

    means = df_fs.groupby(history)[parameters].mean()
    means_all = pd.DataFrame(df_fs[parameters].mean(), columns=['all_']).T
    means = pd.concat([means, means_all])

    deviations = demo_means_ts.sub(means, level=history)

    wage_index = pd.concat([deviations.xs(0, level=history).dot(params.iloc[1:]),
                            deviations.xs(1, level=history).dot(params.iloc[1:]),
                            deviations.xs('all_', level=history).dot(params.iloc[1:])],
                           axis=1, keys=['from_e', 'from_n', 'all_']).diff().stack(dropna=False).shift(-3)
    wage_index.name = 'wage_index'

    lrprod_reindexed = lrprod.reindex(index=wage_index.index, level='qmonth')
    df_ss = pd.concat([pd.DataFrame(wage_index), lrprod_reindexed], axis=1)
    dummies = pd.get_dummies(df_ss.index.map(lambda x: x[0].quarter), prefix='Q')
    dummies.index = df_ss.index
    df_ss = pd.concat([df_ss, dummies], axis=1)

    df_ss = df_ss.unstack().reorder_levels([1, 0], axis=1).sort_index(axis=1)
    return df_ss
