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

# workplace parking assumptions
parking_prob ={
    'workplace':{
        'car':{
            'min_prob_bldg_dsty':0.5,
            'min_prob':0.05,
            'max_prob_bldg_dsty':0.05,
            'max_prob':1.0
        },
        'motorcycle':{
            'min_prob_bldg_dsty':0.5,
            'min_prob':0.2,
            'max_prob_bldg_dsty':0.05,
            'max_prob':1.0
        }
    },
    'home':{
        'car':{
            'min_prob_bldg_dsty':0.5,
            'min_prob':0.1,
            'max_prob_bldg_dsty':0.05,
            'max_prob':1.0
        },
        'motorcycle':{
            'min_prob_bldg_dsty':0.5,
            'min_prob':0.4,
            'max_prob_bldg_dsty':0.05,
            'max_prob':1.0
        }
    }
}
