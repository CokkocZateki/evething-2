# 
corporation_wallets = """
SELECT  cw.corporation_id, c.name, cw.account_key, cw.description, cw.balance
FROM    thing_corpwallet cw
INNER JOIN thing_corporation c ON c.id = cw.corporation_id
WHERE   corporation_id IN (
    SELECT  DISTINCT c.corporation_id
    FROM    thing_character c
    INNER JOIN thing_apikey ak ON c.apikey_id = ak.id
    WHERE ak.user_id = %s
)
ORDER BY c.name, cw.account_key
"""

order_aggregation = """
SELECT  mo.character_id,
        c.name,
        COUNT(mo.order_id) AS orders,
        COALESCE(SUM(CASE WHEN mo.corp_wallet_id IS NULL THEN 1 END), 0) AS personal_orders,
        COALESCE(SUM(CASE WHEN mo.corp_wallet_id IS NOT NULL THEN 1 END), 0) AS corp_orders,
        COALESCE(SUM(CASE mo.buy_order WHEN true THEN 1 END), 0) AS buy_orders,
        COALESCE(SUM(CASE mo.buy_order WHEN true THEN mo.total_price END), 0) AS total_buys,
        COALESCE(SUM(CASE mo.buy_order WHEN false THEN 1 END), 0) AS sell_orders,
        COALESCE(SUM(CASE mo.buy_order WHEN false THEN mo.total_price END), 0) AS total_sells,
        COALESCE(SUM(mo.escrow), 0) AS total_escrow
FROM    thing_marketorder mo, thing_character c, thing_apikey_characters ac, thing_apikey a
WHERE   mo.character_id = c.id
        AND c.id = ac.character_id
        AND ac.apikey_id = a.id
        AND a.user_id = %s
GROUP BY mo.character_id, c.name
ORDER BY c.name
"""

# BPCalc movement calculation
bpcalc_movement = """
SELECT  item_id, CAST(SUM(movement) / 30 * %%s AS decimal(18,2))
FROM    thing_pricehistory
WHERE   item_id IN (%s)
        AND date >= %%s
GROUP BY item_id
"""

# item_ids for a specific user's BlueprintInstance objects and related components
user_item_ids = """
SELECT  bp.item_id
FROM    thing_blueprint bp, thing_blueprintinstance bpi
WHERE   bp.id = bpi.blueprint_id
        AND bpi.user_id = %s
UNION
SELECT  item_id
FROM    thing_blueprintcomponent
WHERE   blueprint_id IN (
            SELECT  blueprint_id
            FROM    thing_blueprintinstance
            WHERE   user_id = %s
)
UNION
SELECT  item_id
FROM    thing_asset ca, thing_character c, thing_apikey_characters ac, thing_apikey a
WHERE   ca.character_id = c.id
        AND c.id = ac.character_id
        AND ac.apikey_id = a.id
        AND a.user_id = %s
"""

# item_ids for all BlueprintInstance objects and related components
all_item_ids = """
SELECT  bp.item_id
FROM    thing_blueprint bp, thing_blueprintinstance bpi
WHERE   bp.id = bpi.blueprint_id
UNION
SELECT  item_id
FROM    thing_blueprintcomponent
WHERE   blueprint_id IN (
            SELECT  blueprint_id
            FROM    thing_blueprintinstance
)
UNION
SELECT  item_id
FROM    thing_asset
"""


# -- api_updater queries --
transaction_insert = """
INSERT INTO thing_transaction (
  station_id,
  item_id,
  character_id,
  transaction_id,
  date,
  buy_transaction,
  quantity,
  price,
  total_price,
  corp_wallet_id,
  other_char_id,
  other_corp_id
)
VALUES
%s
"""

transaction_insert_part = '(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)'
