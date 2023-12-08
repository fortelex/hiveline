import pandas as pd

# filter by year
def filter_year(df, year):
    df = df[df['TIME_PERIOD']==year]
    df = df.drop(columns='TIME_PERIOD')
    return df.reset_index(drop=True)

# filter by max precision
def filter_precision(df):
    df = df[df['geo'].apply(len)<=5]
    max_precision = df['geo'].apply(len).max()
    df = df[df['geo'].apply(len)==max_precision]
    return df.reset_index(drop=True), max_precision-2

# rename geo and OBS_VALUE columns
def rename_cols(df, obs_value_name, resolution):
    df = df.rename(columns={'geo': f'nuts{resolution}', 'OBS_VALUE': obs_value_name})
    return df

def df_to_percent(df, index):
    '''
    Replace values by percentages per row
    Args:
        df (DataFrame): the dataframe to transform
        index (str): the name of the column to consider as index
    Returns:
        the same dataframe with values in percentages 
    '''
    df = df.set_index(index)
    df = df.div(df.sum(axis=1), axis=0)
    return df.reset_index()

def clean_age(df_age, precision):
    # drop useless columns
    df_age.drop(columns=['TIME_PERIOD', 'STRUCTURE', 'STRUCTURE_ID', 'freq', 'sex', 'unit', 'OBS_FLAG'], inplace=True)
    df_age = rename_cols(df_age, 'count', precision)

    # regroup age ranges
    under_20 = ['Y_LT5', 'Y5-9', 'Y10-14', 'Y15-19']
    between_20_64 = ['Y20-24', 'Y25-29', 'Y30-34', 'Y35-39', 'Y40-44', 'Y45-49', 'Y50-54', 'Y55-59', 'Y60-64']
    over_64 = ['Y65-69', 'Y70-74', 'Y75-79', 'Y80-84', 'Y85-89', 'Y_GE90']

    df_under_20 = df_age[df_age['age'].isin(under_20)].groupby('nuts3').sum().reset_index()
    df_under_20.rename(columns={'count':'age_under_20'}, inplace=True)

    df_between_20_64 = df_age[df_age['age'].isin(between_20_64)].groupby('nuts3').sum().reset_index()
    df_between_20_64.rename(columns={'count':'age_between_20_64'}, inplace=True)

    df_over_64 = df_age[df_age['age'].isin(over_64)].groupby('nuts3').sum().reset_index()
    df_over_64.rename(columns={'count':'age_over_64'}, inplace=True)

    df_age_export = pd.merge(df_under_20, df_between_20_64, on='nuts3')
    df_age_export = pd.merge(df_age_export, df_over_64, on='nuts3')

    return df_age_export

def clean_employment_rate(df_employment, precision):
    # drop useless columns
    df_employment.drop(columns=['TIME_PERIOD', 'STRUCTURE', 'STRUCTURE_ID', 'freq', 'sex', 'unit', 'OBS_FLAG'], inplace=True)
    df_employment = rename_cols(df_employment, 'employment_rate', precision)
    
    df_between_20_64 = df_employment[df_employment['age']=='Y20-64'].groupby('nuts2').sum().reset_index()
    df_between_20_64.rename(columns={'employment_rate':'employment_rate_between_20_64'}, inplace=True)

    df_over_64 = df_employment[df_employment['age']=='Y_GE65'].groupby('nuts2').sum().reset_index()
    df_over_64.rename(columns={'employment_rate':'employment_rate_over_64'}, inplace=True)

    df_employment_export = pd.merge(df_between_20_64, df_over_64, on='nuts2')
    return df_employment_export

def clean_employment_type(df_employment_type, precision):
    # drop useless columns
    df_employment_type.drop(columns=['TIME_PERIOD', 'STRUCTURE', 'STRUCTURE_ID', 'freq', 'unit', 'OBS_FLAG', 'wstatus'], inplace=True)
    df_employment_type = rename_cols(df_employment_type, 'employment_thousand_persons', precision)

    # pivot
    df_employment_type_pivot = df_employment_type.pivot(index='nuts3', columns='nace_r2', values='employment_thousand_persons' )
    df_employment_type_pivot.reset_index(inplace=True)
    df_employment_type_pivot = df_employment_type_pivot.rename_axis(None, axis=1)
    df_employment_type_pivot = df_employment_type_pivot.rename(columns={
        'A': 'Agriculture',
        'B-E': 'Industry',
        'F': 'Construction',
        'G-I': 'Wholesale, retail trade, transport, accomodation and food service',
        'J': 'Information and communication',
        'K': 'Finance, insurance',
        'L': 'Real estate',
        'M_N': 'Professional, scientific and technical, administrative',
        'O-Q': 'Public administration, defence, education, health, social',
        'R-U': 'Arts, entertainment, other service',
        })
    df = df_to_percent(df_employment_type_pivot.copy().dropna(), 'nuts3')
    # missing mean imputation 
    # regroup types
    df['agricultural'] = df['Agriculture']
    df['industrial'] = df['Industry'] + df['Construction']
    df['commercial'] = df['Wholesale, retail trade, transport, accomodation and food service'] + df['Real estate'] + df['Arts, entertainment, other service']
    df['office'] = df['Information and communication'] + df['Finance, insurance'] + df['Professional, scientific and technical, administrative']
    df['social'] = df['Public administration, defence, education, health, social']
    df = df[['nuts3', 'agricultural', 'industrial', 'commercial', 'office', 'social']]
    # add prefix
    df = df.rename(columns={c: 'employment_type_'+c if c != 'nuts3'else c for c in df.columns})
    return df

def clean_motorization(df_motor, precision, clean_df_age):
    df_motor.drop(columns=['TIME_PERIOD', 'STRUCTURE', 'STRUCTURE_ID', 'freq', 'unit', 'OBS_FLAG'], inplace=True)
    df_motor = rename_cols(df_motor, 'count', precision)
    
    # cars are sometimes informed a second time with a vey small value
    # the largest is kept
    cars = df_motor[df_motor['vehicle']=='CAR'].groupby('nuts2').max().reset_index()
    df_motor = df_motor[df_motor['vehicle']!='CAR']
    df_motor = pd.concat([df_motor, cars])

    # pivot
    df_motor_pivot = df_motor.pivot(index='nuts2', columns='vehicle', values='count' )
    df_motor_pivot.reset_index(inplace=True)
    df_motor_pivot = df_motor_pivot.rename_axis(None, axis=1)

    # get the number of inhabitants per nuts2 to compute the vehicle/inhabitant
    df_inhabitants = clean_df_age.copy()
    df_inhabitants['nuts2'] = df_inhabitants['nuts3'].apply(lambda s: s[:-1])
    df_inhabitants['over_20'] = df_inhabitants['age_between_20_64'] + df_inhabitants['age_over_64']
    df_inhabitants = df_inhabitants[['nuts2', 'over_20']]
    df_inhabitants = df_inhabitants.groupby('nuts2').sum().reset_index()

    df_motor_pivot = df_motor_pivot.merge(df_inhabitants, on="nuts2")
    df_motor_pivot = df_motor_pivot.set_index('nuts2')
    df_motor_export = df_motor_pivot.div(df_motor_pivot['over_20'], axis=0)
    df_motor_export.reset_index(inplace=True)

    # missing mean imputation

    # regroup lorries and road tractors 
    # regroupment has to be done after replacing missing values, otherwise it can group NaN with a valid number
    df_motor_export['vehicle_truck'] = df_motor_export['LOR'] + df_motor_export['TRC']
    # drop total and trailers
    df_motor_export.drop(columns=['TOT_X_TM', 'TRL_STRL', 'LOR', 'TRC', 'over_20'], inplace=True)
    # rename columns
    df_motor_export = df_motor_export.rename(columns={
        'CAR': 'vehicle_car',
        'MOTO': 'vehicle_moto',
        'SPE': 'vehicle_special',
        'BUS_TOT': 'vehicle_bus',
        'UTL': 'vehicle_utilities',
    })

    return df_motor_export