#from pedido import prazo_pedido, quantidade_pedido, posicao_pedido
#from func_custo import depositos_prox
from functions_database import get_stock_per_drink, get_stock_per_cluster, get_stock_total, get_clusters
#from cluster import clusters
import pandas as pd
import pdb
from calculateDistances import deliveries

"""
Legenda:
- prazo_pedido: Data que o cliente pediu como prazo
- quantidade_pedido: Dataframe com index sendo a bebida e uma coluna sendo a quantidade referente a cada bebida
- posicao_pedido: longitude e latitude do cliente

- depositos_prox: Dataframe com id de cada deposito mais proximos(menos custosos) ao pedido, 
                  além do custo e tempo para chegar relativo a cada depósito. Consideramos que todos os
                  depositos presentes nesse DataFrame fazem entrega em D+0



- get_stock_per_drink(id): Retorna o DataFrame com o número de cada bebida presente no estoque do cdd baseado no id
- get_stock_per_cluster(id): Retorna o DataFrame com o número de cada cluster presente no estoque do cdd baseado no id

"""

# Supondo clusters como, por exemplo, {bronze:[skol, brahma, antartica], prata:[bud, original, stella],
#                                       ouro:[colorado, corona, leffe]}
def order_cluster(clusters, order):
    """
    Função para a separação das bebidas comandadas em clusters

    :param clusters: DataFrame de clusters de bebidas da Ambev
    :param quantidade_pedido: DataFrame com tipo e quantidade de cada bebida da comanda
    :return: clusters_command: DataFrame com o nome do cluster e a quantidade de bebidas presentes do pedido
    """

    for cluster,row in clusters.iterrows():
        names = clusters.loc[cluster,"name"]
        order.loc[order.index.isin(names),"cluster"] = cluster
    order["cluster"] = order["cluster"].astype(int)
    clusters_command = order.groupby("cluster").agg('sum')
    
    return order,clusters_command

def exist_stock(depo_close, clusters_command, order):
    """    
    Função que consulta o estoque dos armazens mais proximos e retorna a condição do estoque:
    1) infull = tem estoque para exatamento o que o cliente pediu
    2) partial = tem estoque parcial, ou seja, existem bebidas suficiente para o mesmo cluster, mas não
        exatamente o que o cliente pediu
    3) none = não há estoque suficiente para o pedido
    
    :param deposito_fav: dataframe com dados sobre quantidade presente para cada bebida e para cada cluster no
                       deposito mais próximo ao cliente
    :param clusters_command: DataFrame com cluster e quantidade desses clusters no pedido
    :param quantidade_pedido: DataFrame com marca e quantidade das bebidas pedidas
    :return: depositos_prox: DataFrame de depositos favoritos atualizado com coluna sobre sua condição
    """
  
    for id,row_depo in depo_close.iterrows():
        stock_drinks = get_stock_per_drink(id)
        stock_drinks.set_index(["drink_name"], inplace=True)
        stock_clusters = get_stock_per_cluster(id)
        stock_clusters.set_index(["cluster"], inplace=True)
        depo_close.loc[id, "condition"] = "infull"
        for drink,row_order in order.iterrows():
            if row_order["quantity"] > stock_drinks.loc[drink, 'quantity']:
                depo_close.loc[id, "condition"] = "partial"
                break
        for cluster,row_order in clusters_command.iterrows():
            if row_order["quantity"] > stock_clusters.loc[cluster,"quantity"]:
                depo_close.loc[id, "condition"] = "none"
                break

    return depo_close

def combine_depo(depo_ranking, order):
    """    
    Função que verifica se os dois maiores depósitos combinados tem estoque suficiente para atender ao pedido
    :param ranking_depositos: DataFrame de depósitos baseado no estoque presente
    :param quantidade_pedido: DataFrame com marca e quantidade das bebidas pedidas
    :return: condition: Flag com True ou False baseado na existência ou não de depósito suficiente 
    """
    ids = depo_ranking.index
    
    id_1 = int(ids[0])
    id_2 = int(ids[1])
    stock_1 = get_stock_per_drink(id_1) #DataFrame com estoque de bebidas do maior deposito
    stock_1.set_index("drink_name", inplace=True)
    stock_2 = get_stock_per_drink(id_2) #DataFrame com estoque de bebidas do segundo maior deposito
    stock_2.set_index("drink_name", inplace=True)
    condition = True
    
    for drink,row in order.iterrows():
        if row['quantity'] > stock_1.loc[drink, "quantity"] + stock_2.loc[drink, "quantity"]:
            pdb.set_trace()
            condition = False
            break

    return condition



def mix_drinks(id_depo, order):
    
    stock_drinks = get_stock_per_drink(id_depo)
    stock_drinks.set_index(["drink_name"], inplace=True)
    deliv = {}

    for drink, row in order.iterrows():
        if order.loc[drink, "quantity"] > stock_drinks.loc[drink,"quantity"]:
            basket = stock_drinks.loc[drink,"quantity"]
            stock_drinks.loc[drink,"quantity"] -= basket
            if drink in deliv.keys(): #suficiente
                deliv[drink] += basket
            else:
                deliv[drink] = basket

            cluster_drink = stock_drinks.loc[drink,"cluster"]
            same_cluster = stock_drinks[(stock_drinks["cluster"] == cluster_drink) & (stock_drinks["quantity"] != 0)]
            same_cluster.sort_values(by=["price"], ascending=True, inplace=True)
            #same_cluster.drop(drink, inplace=True)
        
            for drink_cluster, row_cluster in same_cluster.iterrows():
                if basket + stock_drinks.loc[drink_cluster,"quantity"] >= order.loc[drink, "quantity"]:
                    add = order.loc[drink, "quantity"]-basket
                    stock_drinks.loc[drink_cluster,"quantity"] -= add
                    basket = order.loc[drink, "quantity"]
                    
                    if drink_cluster in deliv.keys(): #suficiente
                        deliv[drink_cluster] += add
                    else:
                        deliv[drink_cluster] = add
                    break
                    
                else:
                    add = stock_drinks.loc[drink_cluster,"quantity"]
                    stock_drinks.loc[drink_cluster,"quantity"] -= add # =0
                    basket += add

                    if drink_cluster in deliv.keys(): #n_suficiente
                        deliv[drink_cluster] += add
                    else:
                        deliv[drink_cluster] = add
                
        else:
         
            if drink in deliv.keys():
                deliv[drink]  += order.loc[drink, "quantity"]
                stock_drinks.loc[drink,"quantity"] -= order.loc[drink, "quantity"]
            else:
                deliv[drink] = order.loc[drink, "quantity"]
                stock_drinks.loc[drink,"quantity"] -= order.loc[drink, "quantity"]

    return deliv
        
    
def bussola(order): #lat e lon
    deliv = deliveries()
    depo_close = deliv.calculateDistances(-23.6, -46.6, 3)
    depo_close.set_index(["id"], inplace=True)

    # Calculo dos clusters presentes no pedido
    clusters = get_clusters()
    order,clusters_command = order_cluster(clusters, order)

    # Estabelecimento do limite de preço para conseguirmos entregar ou não no dia D
    # preco_total = quantidade_pedido['preco'].sum()

    # DataFrame que rankeia depositos baseado no total de estoque presente
    for id in depo_close.index:
        depo_close.loc[id,"nb_stock"] = get_stock_total(id)

    depo_close["nb_stock"] = depo_close["nb_stock"].astype(int)
    depo_close.sort_values(by=["nb_stock"], inplace=True, ascending=False, ignore_index=False)

    # Acrescentada condição de cada deposito: 'infull', 'partial' ou 'none'
    depo_close = exist_stock(depo_close, clusters_command, order)

    # DataFrame reorganizado para ter uma ordem baseado no custo de cada deposito para o cliente
    depo_close.sort_values(by=['price'], axis=0, inplace=True)
    
    if not depo_close[depo_close['condition'] == "infull"].empty:
        print("Entregaremos seu pedido em algumas horas")

    elif not depo_close[depo_close['condition'] == "partial"].empty:
        combine= combine_depo(depo_close, order)
        depo_partial = depo_close[depo_close["condition"] == "partial"]
        
        ids = depo_partial.index
        id_depo = int(ids[0])
        deliv = mix_drinks(id_depo, order)
    
        if combine:
            print("Temos duas opções pra você: Entregamos hoje com um frete um pouco maior ou propomosa seguinte \
                  combinação:", deliv)
        
        else:
            print("Para preservar sua entrega hoje, propomos a seguinte combinação:", deliv)
            print("O que acha?")

    else:
        print("Entregaremos apenas amanhã, mas temos um desconto especial para você")

if __name__ == "__main__":
    order = pd.DataFrame({"drink":['Antarctica Originial', "Budweiser", "Guarana Antarctica", 
    "Energetico Fusion Normal", "Energetico Fusion Pessego"], "quantity":[100, 50, 300, 120, 210]})
    order.set_index(["drink"], inplace=True)
    
    bussola(order)


#Pegar bebidas mais baratas entre as disponíveis
#Colocar preço de produto mais frete no retorno ao cliente
#Precisa popular mais o dataframe pois só tem 4 stocks
#Consertar o "Originial"