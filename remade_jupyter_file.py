import pandas as pd
import copy
import json
import numpy as np
import datetime
import pyprind
import requests
from datetime import datetime
import time

print('''Comparing bonuses from  i18 and file...\n
Enter directory and initial file name or press enter for default.\n
Sample: disk:/directory/file.xlsx''')

init_dir_file = input('') or 'I:/payment distribution v1.01.xlsx'
sheet_name = input('Enter sheet name: ') or 'for_test'

print('Parsing data...')
excel_data = pd.read_excel(init_dir_file,
                           sheet_name=sheet_name)

# getting number of columns and rows
bonus_shape = excel_data.shape
# getting number of last company
last_company_column = bonus_shape[1] - 25

# tax_number (inn) row to future header
excel_data.iloc[2, 17:last_company_column] = excel_data.iloc[0, 17:last_company_column]

# changing header, skipping rows
excel_data.columns = excel_data.iloc[2]
excel_data = excel_data.iloc[3:]


# filtering dataframe

excel_data = excel_data[(excel_data["Payment number"].astype('str').str.lower() != "по акту")
                        & ((excel_data["Распределен"].str.lower() == 'ок') |
                           (excel_data["Распределен"].str.lower() == 'ok'))
                        ]

# resetting index
excel_data = excel_data.reset_index(drop=True)

# leaving just right columns
excel_data = excel_data.iloc[:, np.r_[excel_data.columns.get_loc("Payment Number"),
                                excel_data.columns.get_loc("Id счета Концерну"),
                                excel_data.columns.get_loc("Распределен"),
                                excel_data.columns.get_loc("Тип договора (агентский или маркетинг)"),
                                excel_data.columns.get_loc("НДС"),
                                17:excel_data.columns.get_loc("Распределен"),
                                bonus_shape[1] - 6:bonus_shape[1]]]

# all columns except last 6 networks
inn_data = excel_data.iloc[:, :-6].melt(id_vars=["Payment number",
                                                 "Id счета Концерну",
                                                 "Распределен",
                                                 "Тип договора (агентский или маркетинг)",
                                                 "НДС"
                                                 ],
                                        var_name="ИНН ЮЛ",
                                        value_name="CУММА ЮЛ")

print('''Choose XLSX file for 'INN' reference. Enter directory and initial file name or press enter for default.\n
Sample: disk:/directory/file.xlsx''')

init_dir_file = input('') or 'I:/!! РАСПРЕДЕЛЕНИЕ БОНУСОВ/new_2021_РАСПРЕДЕЛЕНИЕ ПЛАТЕЖЕЙ v1.01.xlsx'
sheet_name = input('Enter sheet name: ') or 'ref_tax_id'

print('Parsing data...')
net_ref = pd.read_excel(init_dir_file,
                        sheet_name=sheet_name)

inn_data['ИНН ЮЛ'] = pd.to_numeric(inn_data['ИНН ЮЛ'])
net_ref['ИНН'] = pd.to_numeric(net_ref['ИНН'])

# grouping text data with ; delimeter
unique_chars = lambda x: '; '.join(x.unique())

inn_group_str = inn_data.astype(str).groupby(['Номер начисления i18', 'ИНН ЮЛ'], as_index=False
                                             ).agg({'Id счета Концерну': unique_chars,
                                                    'Распределен': unique_chars,
                                                    'Тип договора (агентский или маркетинг)': unique_chars,
                                                    'НДС': unique_chars})

# grouping sum
inn_group_sum = inn_data.groupby(['Номер начисления i18', 'ИНН ЮЛ'],
                                 as_index=False).agg({'CУММА ЮЛ': 'sum'})

inn_group_sum = pd.merge(inn_group_sum, net_ref,
                         how='left',
                         left_on='ИНН ЮЛ',
                         right_on='ИНН').drop(columns=['ИНН'])

inn_group_sum['CУММ_СЕТЬ_НАЧИСЛЕНИЕ'] = inn_group_sum.groupby(['Номер начисления i18', 'Сеть']
                                                              )['CУММА ЮЛ'].transform('sum')

inn_group_sum = inn_group_sum.rename(columns={"Сеть": "СЕТЬ_СПР"})

inn_group_sum['ИНН ЮЛ'] = pd.to_numeric(inn_group_sum['ИНН ЮЛ'])
inn_group_sum['Номер начисления i18'] = pd.to_numeric(inn_group_sum['Номер начисления i18'])
inn_group_str['ИНН ЮЛ'] = pd.to_numeric(inn_group_str['ИНН ЮЛ'])
inn_group_str['Номер начисления i18'] = pd.to_numeric(inn_group_str['Номер начисления i18'])

inn_group = pd.merge(inn_group_str, inn_group_sum,
                     how='outer',
                     on=['Номер начисления i18', 'ИНН ЮЛ'])

# parsing network "direct contracts"

direct_agr = excel_data.iloc[:, np.r_[excel_data.columns.get_loc("Номер начисления i18"),
                                excel_data.shape[1] - 6:excel_data.shape[1]]]

direct_agr = direct_agr.melt(id_vars="Номер начисления i18",
                             var_name="СЕТЬ_ПРЯМ",
                             value_name="CУММА_ПО_ПРЯМ")

direct_agr = direct_agr.groupby(['Номер начисления i18', 'СЕТЬ_ПРЯМ'], as_index=False).agg({'CУММА_ПО_ПРЯМ': 'sum'})

full_ex_d = pd.merge(inn_group, direct_agr,
                     how='left',
                     left_on=['Номер начисления i18', 'СЕТЬ_СПР'],
                     right_on=['Номер начисления i18', 'СЕТЬ_ПРЯМ'])

print('Parsing API data...')
print('Defining token for i18-API...')
print("Enter login and password for i18"
      "authentication or press 'Enter' for default...")
login_i18 = input('Login: ') or '___'
password_i18 = input('Password: ') or '___'

data_text = '{"login": "' + login_i18 + '", "password": "' + password_i18 + '"}'


def get_token():
    a = requests.get('https://smth___',
                     data=data_text)
    return a.json()['token']


start_time = datetime.now()

# dataframe variable structure
bonuses = pd.DataFrame()

bonus_ids = list(set(pd.read_excel('tax_inn.xlsx')['Номер начисления i18'].to_list()))
bar = pyprind.ProgBar(len(bonus_ids))

for ids in range(len(bonus_ids)):

    token = get_token()

    print(bonus_ids[ids])

    try:

        r = requests.get('JSON_URL',
                         data=json.dumps({'token': token,
                                          'id': bonus_ids[ids]
                                          }))

        bonuses_ = pd.DataFrame(r.json()['data']['items'])

    except:
        time.sleep(1)
        try:
            r = requests.get('JSON_URL',
                             data=json.dumps({'token': token,
                                              'id': bonus_ids[ids]
                                              }))
# gotta figure out what that is
            bonuses_ = pd.DataFrame(r.json()['data']['items'])

        except:
            print(r.text)

    bonuses = bonuses.append(bonuses_, sort=False)
    bar.update()
# time.sleep(1)

print(bonuses)
print(datetime.now() - start_time)

# bonuses_x = pd.concat([pd.DataFrame(pd.json_normalize(x)) for x in bonuses['legal_entities']],ignore_index=True)
# bonuses_x
bonuses_x = bonuses[['ic_id','legal_entities']]
# splitting up JSON data by columns
bonuses_x = pd.DataFrame([dict(y, ic_id=i) for i, x in bonuses_x.values.tolist() for y in x])

# bonuses_x = pd.DataFrame([y for x in bonuses["legal_entities"].values.tolist() for y in x])
# bonuses_x

bonuses_x.to_excel('d:/projects/test_bonus/bonuses_x.xlsx')

bonuses_4col = bonuses_x[['ic_id','legal_entity_inn','network','sum_network']]
bonuses_4col = bonuses_4col.rename(columns={"sum_network": "sum_inn"})
#bonuses_4col['sum_inn'] = pd.to_numeric(bonuses_4col['sum_inn'])

bonuses_4col[['ic_id', 'legal_entity_inn', 'sum_inn']] = bonuses_4col[['ic_id',
                                                                       'legal_entity_inn',
                                                                       'sum_inn']].apply(pd.to_numeric,
                                                                                         errors='raise')
# check for duplicate network
bonuses_4col_str = bonuses_4col.astype(str).groupby(['ic_id', 'legal_entity_inn'], as_index=False
                                             ).agg({'network':unique_chars})

bonuses_4col_str[['ic_id', 'legal_entity_inn']] = bonuses_4col_str[['ic_id', 'legal_entity_inn']].apply(pd.to_numeric,
                                                                                         errors='raise')

#grouping sum
bonuses_4col = bonuses_4col.groupby(['ic_id', 'legal_entity_inn'],
                                 as_index=False).agg({'sum_inn': 'sum'}).apply(pd.to_numeric,
                                                                              errors='raise')

bonuses_4col = pd.merge(bonuses_4col,
                       bonuses_4col_str,
                       how='left',
                       on=['ic_id', 'legal_entity_inn'])


bonuses_4col['sum_network'] = bonuses_4col.groupby(['ic_id',
                                                    'network'])['sum_inn'
                                                               ].transform('sum')

final_df = pd.merge(full_ex_d, bonuses_4col,
                    how='outer',
                    left_on=['Номер начисления i18', 'ИНН ЮЛ'],
                    right_on=['ic_id',	'legal_entity_inn'])

final_df['Сверка привязки ЮЛ к сети'] = np.where(final_df['СЕТЬ_СПР'] == final_df['network'], 0, 1)
final_df[['CУММА ЮЛ',
          'CУММ_СЕТЬ_НАЧИСЛЕНИЕ',
          'sum_inn',
          'sum_network']] = final_df[['CУММА ЮЛ',
                                      'CУММ_СЕТЬ_НАЧИСЛЕНИЕ',
                                      'sum_inn',
                                      'sum_network']].fillna(0)

final_df['Сверка суммы ЮЛ, руб.'] = final_df['CУММА ЮЛ'] - final_df['sum_inn']

final_df['Сверка суммы ЮЛ, %'] = (final_df['CУММА ЮЛ'] / final_df['sum_inn']) - 1

final_df['Сверка суммы ЮЛ Итог'] = np.where(
    (final_df['Сверка суммы ЮЛ, руб.'].abs() > 6000) | (final_df['Сверка суммы ЮЛ, %'].abs() > 0.02), 1, 0)

final_df['Сверка суммы сети, руб.'] = final_df['CУММ_СЕТЬ_НАЧИСЛЕНИЕ'] - final_df['sum_network']
final_df['Сверка суммы сети, %'] = final_df['CУММ_СЕТЬ_НАЧИСЛЕНИЕ'] / final_df['sum_network'] - 1

final_df['Сверка суммы сети Итог'] = np.where((final_df['Сверка суммы сети, руб.'].abs() > 6000)
                                              | (final_df['Сверка суммы сети, %'].abs() > 0.02), 1, 0)

final_df['Кол-во ошибок'] = final_df['Сверка привязки ЮЛ к сети'] + final_df['Сверка суммы ЮЛ Итог'] + final_df[
    'Сверка суммы сети Итог']

final_df
# conds = [((final_df['sum_inn']==0) & (final_df['CУММА ЮЛ'].abs()>0)),
#         # ((final_df["sum_inn"]==0) & (final_df["СУММА ЮЛ"]==0)),
#          (final_df['sum_inn']!=0)]

# conds_vals = [-1, (final_df['sum_inn']/final_df['СУММА ЮЛ'])-1]

# final_df['Сверка суммы ЮЛ, %'] = np.select(conds, conds_vals)


# # final_df['Сверка суммы ЮЛ, %'] = np.where(((final_df['sum_inn']==0) & (final_df['CУММА ЮЛ'].abs()>0)), -1, 0)
# # final_df['Сверка суммы ЮЛ, %'] = np.where(((final_df['sum_inn']==0) & (final_df['СУММА ЮЛ']==0), 0, 1)
# final_df

# #                                           np.where(((final_df['sum_inn']==0) & (final_df['СУММА ЮЛ']==0)),
# #                                                    0, (final_df['sum_inn']/final_df["СУММА ЮЛ"])-1))


# final_df['Сверка суммы ЮЛ, %'] = final_df['Сверка суммы ЮЛ, %'].round(2)


final_df.to_excel('d:/projects/test_bonus/final_df.xlsx')

print('Done.')

