import streamlit as st
import requests
import pandas as pd
from bs4 import BeautifulSoup
from sqlalchemy import create_engine
import psycopg2 
import io
import codecs
from pandas_profiling import ProfileReport
import streamlit.components.v1 as components
from streamlit_pandas_profiling import st_profile_report
from IPython.display import HTML
import base64
from io import BytesIO

#### CONFIGURAÇÃO DO DATABASE
engine = create_engine(st.secrets["db"])
schema = 'public'
tabela_notas = "nfc_e"


#### CONFIGURAÇÃO DA EXPORTAÇÃO PARA EXCEL
def to_excel(df):
    output = BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    df.to_excel(writer, sheet_name='Sheet1')
    writer.save()
    processed_data = output.getvalue()
    return processed_data

def get_table_download_link(df):
    """Generates a link allowing the data in a given panda dataframe to be downloaded
    in:  dataframe
    out: href string
    """
    val = to_excel(df)
    b64 = base64.b64encode(val)
    return f'<a href="data:application/octet-stream;base64,{b64.decode()}" download="Your_File.xlsx">Download Excel file</a>'


#### GERENCIAMENTO USUARIOS
def create_userstable():
    sql_command = ('CREATE TABLE IF NOT EXISTS userstable(username TEXT, password TEXT)')
    with engine.connect() as con:
        rs = con.execute(sql_command)

def add_userdata(data, tablename):
    '''Novo Usuáro: dataframe, table name''' 
    data.head(0).to_sql(tablename, engine, if_exists='append',index=False) #truncates the table
    conn = engine.raw_connection()
    cur = conn.cursor()
    output = io.StringIO()
    data.to_csv(output, sep='\t', header=False, index=False)
    output.seek(0)
    contents = output.getvalue()
    cur.copy_from(output, '"'+tablename+'"', null="") # null values become ''
    conn.commit()

def login_user(engine, username, password):
    sql_command1 = ("SELECT * FROM userstable WHERE username = '{}' AND password = '{}'".format(username,password))
    #print (sql_command1)
    df = pd.read_sql_query(sql_command1, con=engine)
    return df
    
def psql_select_table_full(engine, schema, table, username):
    ''' SELECT FULL'''
    schema1 = '"'+ schema +'"'
    table1  = '"'+ table +'"'
    username1 = '"username"' 
    sql_command1 = ("SELECT * FROM {}.{} WHERE username = '{}'".format(schema,table,username.lower()))
    #print (sql_command1)
    df = pd.read_sql_query(sql_command1, con=engine)
    conn = engine.raw_connection()
    conn.commit()
    return df

#### CONFIGURAÇÃO DA BASE
def psql_select_table(engine, schema, table, campo, filtro, username):
    schema1 = '"'+ schema +'"'
    table1  = '"'+ table +'"'
    campo1 = '"' + campo +'"'
    username1 = '"username"' 
    sql_command1 = ("SELECT * FROM {}.{} WHERE {}.{} = '{}' AND {}.{} = '{}'".format(schema1.lower(),table1.lower(),table1.lower(),campo1,filtro, table1.lower(),username1,username))
    print (sql_command1)
    df = pd.read_sql_query(sql_command1, con=engine)
    conn = engine.raw_connection()
    conn.commit()
    return df

def psql_appennd_table(data, tablename):
    data.head(0).to_sql(tablename, engine, if_exists='append',index=False) #truncates the table
    conn = engine.raw_connection()
    cur = conn.cursor()
    output = io.StringIO()
    data.to_csv(output, sep='\t', header=False, index=False)
    output.seek(0)
    contents = output.getvalue()
    cur.copy_from(output, '"'+tablename+'"', null="") # null values become ''
    conn.commit()

#### TRATAMENTO DE DADOS
def trata_dtNote(se_dtNota):
    df_TABLE_8=pd.DataFrame(se_dtNota.str.split(expand=True))
    result = df_TABLE_8.iloc[0,8]#.replace("/", "_")
    return result

def trataEstabelecinento(se_Estabelecimento):
    df_TABLE_5=pd.DataFrame(se_Estabelecimento.str.split(expand=True))
    df_TABLE_5.iloc[0].fillna(' ')
    result = ' '.join(df_TABLE_5.iloc[0].fillna(' ').values)
    return result

def trataConsumidor(se_Consumidor):
    sTABLE_9 = se_Consumidor.values.reshape(1,2)
    col=["CONSUMIDOR", "documento"]
    df_TABLE_9=pd.DataFrame(sTABLE_9, columns=col)
    result = df_TABLE_9.iloc[0,1].replace(" ", "").replace("\n", "").replace(":", "_")
    return(result)

def trataNFCe(se_NFC):
    sTABLE_10 = se_NFC.values.reshape(int(se_NFC.size/6),6)
    headers=['Codigo', 'Descricao', 'Qtde', 'Un', 'Vl_Unit', 'Vl_Total']
    df_TABLE_10=pd.DataFrame(sTABLE_10[1:], columns=headers)
    df_TABLE_10['Vl_Total'] = df_TABLE_10['Vl_Total'].replace(',','.', regex=True).astype(float)
    df_TABLE_10['Vl_Unit'] = df_TABLE_10['Vl_Unit'].replace(',','.', regex=True).astype(float)
    return df_TABLE_10


#### SCRAP DA NOTA
@st.cache
def scrap_nfce(req):
    soup = BeautifulSoup(req.text, 'html.parser')
    tables = soup.find_all('table')
    cnt = 0
    se_Estabelecimento = pd.Series()
    se_Consumidor = pd.Series()
    se_NFC = pd.Series()
    se_dtNota = pd.Series()
    #df = pd.DataFrame()
    for my_table in tables:
        cnt += 1
        #print ('=============== TABLE {} ==============='.format(cnt))
        rows = my_table.find_all('tr', recursive=False) 
        for row in rows:
            cells = row.find_all(['th', 'td'], recursive=False)
            for cell in cells:
                # VERIFICAÇÃO DAS TABELAS
                #print (cell.string)
                if cnt==5:
                    if cell.string:
                        se_Estabelecimento=se_Estabelecimento.append(pd.Series(cell.text))
                if cnt==9:
                    if cell.string:
                        se_Consumidor=se_Consumidor.append(pd.Series(cell.text).str.strip())
                if cnt==10:
                    if cell.string:
                        se_NFC=se_NFC.append(pd.Series(cell.text))
                if cnt==8:
                    if cell.string:
                        se_dtNota=se_dtNota.append(pd.Series(cell.text))        
    df = trataNFCe(se_NFC)
    df['Identificacao'] = trataConsumidor(se_Consumidor)
    df['Estabelecimento'] = trataEstabelecinento(se_Estabelecimento)
    df['data_nota'] = trata_dtNote(se_dtNota)
    df['data_nota'] = pd.to_datetime(df['data_nota'], infer_datetime_format=True)
    #return se_Estabelecimento, se_Consumidor, se_NFC, se_dtNota
    return df


####INTERFACE:
def main():
    """"PARSE DA NFC-E"""
    st.title("Perfil de Compras")
    menu = ["HOME", "LOGIN", "CRIAR CONTA", "SOBRE"]
    choice = st.sidebar.selectbox("Menu", menu)
    if choice == "HOME":
        st.subheader("Faz a analise das NFC-E/RS, e retorna uma análise de consumo do consumidor, além de possibilitar a exportação da NFC-e para Excel")
        st.subheader("Para iniciar faça login no Menu a esquerda.")


    elif choice == "LOGIN":
        st.subheader("Página de Autenticação no Sistema")
        username = st.sidebar.text_input("User Name")
        password = st.sidebar.text_input("Password", type='password')
        if st.sidebar.checkbox("<- Marque para iniciar o Login"):
            ####st.dataframe(result)
            if not login_user(engine, username, password ).empty:
                #password is true:
                st.info("Bem vindo: {}".format(username))
                task = st.selectbox("Task", ["Adicionar Nova Nota", "Anaytics", "Gerenciar Usuários"])
                if task == "Adicionar Nova Nota":
                    st.subheader("Adicione a URL da nota abaixo:")
                    txt_url_nfce  = st.text_input("URL NFC-E:")
                    ##url inteira:
                    url = txt_url_nfce.title()
                    ##retira só o parâmetro:
                    p = url[url.find("?P=")+3:url.find("?P=")+110]
                    if st.button("Enviar"):
                        st.subheader("enviando...")
                        df_nota = psql_select_table(engine, schema, tabela_notas, "p", p.lower(), username)
                        st.dataframe(df_nota)
                        if len(df_nota.index.values) == 0:
                            print('DataFrame is empty!')
                            url = 'https://www.sefaz.rs.gov.br/ASP/AAE_ROOT/NFE/SAT-WEB-NFE-NFC_QRCODE_1.asp?p='+ p
                            st.text(url)
                            req = requests.get(url)
                            if req.status_code == 200 and p:
                                df_nota = scrap_nfce(req)
                                st.success('Requisicao bem sucedida!')
                                df_nota["url"] = url.lower()
                                df_nota["p"] = p.lower()
                                df_nota["username"] = username.lower()
                                ###st.text(df_nota.count())
                                st.markdown(get_table_download_link(df_nota), unsafe_allow_html=True)
                                psql_appennd_table(df_nota,tabela_notas)
                                st.text("DB atualizado....")
                            else:
                                st.warning("Algo deu errado da REQUISIÇÃO :(")
                        else:
                            ###df_nota está no DATABASE
                            st.success('Nota já cadastrada! Carregando...')
                        ###EXIBE DATAFRAME DA NOTA
                        st.dataframe(df_nota)
                        st.text("Total da Nota {}".format(df_nota['Vl_Total'].sum()))
                    ############################## 
                    #Adicionar um novo Post
                elif task =="Anaytics":
                    st.subheader("Analytics....")
                    if st.button("Enviar"):
                        df_analytics = psql_select_table_full(engine, schema, tabela_notas, username)
                        if df_analytics.empty:
                            st.text("NENHUMA NOTA CADASTRADA COM ESSE USUÁRIO")
                        else:
                            st.text("download")
                            st.markdown(get_table_download_link(df_analytics), unsafe_allow_html=True)
                            st.dataframe(df_analytics)
                            st.text("Total  {}".format(df_analytics['Vl_Total'].sum()))
                            data = df_analytics.iloc[:, 0:-3]
                            exclude_unique = list(data.columns[data.nunique() <= 1])
                            data = data[[col for col in data.columns if col not in exclude_unique]]
                            profile = ProfileReport(data)
                            st_profile_report(profile)
                    ############################## 
                    #Analytics
                elif task =="Gerenciar Usuários":
                    st.subheader("Gerenciar Usuários....")
                    ############################## 
                    #Gerenciar Usuários
                    #user_result = view_all_users()
                    #clean_db = pd.DataFrame(user_result, columns=["USERNAME", "PASSWORD"])
                    #st.dataframe(clean_db)
            else:
                st.warning("Incorrect Username/Password")

    elif choice == "CRIAR CONTA":
        st.subheader("Criar nova conta de usuário:")
        new_user = st.text_input("Nome do Usuário:")
        new_password = st.text_input("Senha:", type='password')
        
        if st.button("Signup"):
            #create_userstable()
            df = pd.DataFrame([[new_user,new_password]], columns=('username', 'password'))
            add_userdata(df, "userstable")
            st.success("Nova Conta de usuário foi criada")
            st.info("Vá para o Menu de LOGIN para acesso")
    elif choice == "SOBRE":
        st.subheader("Sobre...")
        if st.button("OBRIGADO!!!"):
            st.balloons()
        
        st.info("Desenvolvido por Paulo Cristiano Klein\n\n"
                "Mantido por [Paulo Klein](https://www.linkedin.com/in/pauloklein/). "
                "Me visite também em https://github.com/Tianoklein")

        html_temp = '''<a href="mailto:tianoklein@hotmail.com?subject=Streamlit NFC-E Parse&body=Tenho uma sugestão: "> <h3>  Duvidas, Criticas, Sugestões ou se quiser me pagar uma cerveja! 😂</h3></a>'''
        components.html(html_temp)   
        


if __name__ == '__main__':
    main()