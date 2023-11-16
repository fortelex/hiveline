data_folder = '../data/'
age_file = data_folder+'age/age_nuts3_2022_clean.csv'
employment_rate_file = data_folder + \
    'employment/employment_rate_nuts2_2022_clean.csv'
employment_type_file = data_folder + \
    'employment/employment_type_nuts3_2020_clean.csv'
income_file = data_folder+'income/households_income_nuts2_2020_clean.csv'
motorization_file = data_folder + \
    'motorization/motorization_proba_nuts2_2020_clean.csv'

# replace points (a store for example) by point_area area value
point_area = 100  # m²
# non empty places are accounted as workplaces according to that coefficient
default_work_coefficient = 0.3
