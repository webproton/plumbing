# parsers/run.py
import sys
import json
from parsers.core.loader import load_rows
from parsers.registry import parse

DEBUG = True


def main():
    if len(sys.argv) < 2:
        print("python run.py file.xlsx")
        return

    file_path = sys.argv[1]

    rows = load_rows(file_path)

    if DEBUG:
        print(f"ROWS LOADED: {len(rows)}")

    result = parse(rows)

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
    
    
    # в 12 накладной в поле банк нейм лезет мусор 
    
    # в 11 определило как  default  а должно быть аквадом и соотвтетсно не опрелелило телеофны поставщика и покупателя  а они есть 
    
    # 7 и 6 and pr.xmlsx накллдадная  там почти пустой документ но это поставщик сантан - сделать под него парсер и опрелелять его из таьбиолцы по контектсу по типу тавра
    
    # в 2538.xls    накладной в поле банк нейм лезет мусор  и    "supplier": null,
    
    #  nakladnaya2.xlsx  определило как  default  а должно быть аквадом и соотвтетсно не опрелелило телеофны поставщика и покупателя  а они есть 
    
    # add read xml 
    
    # поставщик секвоя
    
    # когда в бд лезет накладная которая выдает  default  предоставить право сразу редактировать  ее там в админке джанго или еще где  и вручную указывать что за поставщик
    # и потом же сразу запомнить и маркировать  последующие похожие по признакам 
