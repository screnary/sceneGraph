import os
import json
from easydict import EasyDict
import numpy as np
import pandas as pd

# parse geojson format
class GeoJsonParser:
    def __init__(self, json_str: str):
        self.original = json_str
        self.parsed_data = None
        self.parse()
    
    def clean_json_string(self, json_str: str) -> str:
        """清理JSON字符串"""
        # 处理转义的单引号
        json_str = json_str.replace("\'", '"')
        
        # 处理外层单引号
        if json_str.startswith("'") and json_str.endswith("'"):
            json_str = json_str[1:-1]
        
        # other formats
        json_str = json_str.replace('"{', '{').replace('}"', '}')
        json_str = json_str.replace('\\n', '')
        json_str = json_str.replace('\\', '')
        
        return json_str
    
    def parse(self):
        """解析JSON数据"""
        try:
            # 清理JSON字符串
            cleaned = self.clean_json_string(self.original)
            
            # 解析外层JSON
            data = json.loads(cleaned)
            
            # 解析geometry字段
            if isinstance(data.get('geometry'), str):
                data['geometry'] = json.loads(data['geometry'])
            
            self.parsed_data = EasyDict(data)
            
        except json.JSONDecodeError as e:
            print(f"JSON解析错误: {e}")
            self.parsed_data = None
    
    def get_coordinates(self):
        """获取所有坐标点"""
        if self.parsed_data and 'geometry' in self.parsed_data:
            return self.parsed_data['geometry'].get('coordinates', [])
        return []
    
    def get_coordinate_bounds(self):
        """获取坐标范围"""
        coordinates = self.get_coordinates()
        if not coordinates:
            return None
        
        lons = [coord[0] for coord in coordinates]
        lats = [coord[1] for coord in coordinates]
        
        return {
            'min_lon': min(lons),
            'max_lon': max(lons),
            'min_lat': min(lats),
            'max_lat': max(lats)
        }
    
    def get_line_length(self):
        """计算线段总长度（简单计算，不考虑地球曲率）"""
        coordinates = self.get_coordinates()
        if len(coordinates) < 2:
            return 0
            
        total_length = 0
        for i in range(len(coordinates)-1):
            # 简单的欧几里得距离
            x1, y1 = coordinates[i]
            x2, y2 = coordinates[i+1]
            length = ((x2-x1)**2 + (y2-y1)**2)**0.5
            total_length += length
            
        return total_length

def analyze_geojson(json_str: str):
    parser = GeoJsonParser(json_str)
    
    if parser.parsed_data:
        return EasyDict({'geometry_type': parser.parsed_data['geometry']['type'], 'bounds': parser.get_coordinate_bounds()})
    

# read csv file and parse
def parse_xls(f_path):
    """
    read xls file and parse to node info list, and save as node list
    """
    if not os.path.exists(f_path):
        return False
    df = pd.read_excel(f_path)
    df_nodes = df[['element_name','data_time','geojson','mean_value','max_value','min_value']]

    pheno_list = []
    for i in range(df.shape[0]):
        pheno_node = EasyDict() # phenomenon node
        pheno_node.type = df_nodes['element_name'][i]
        pheno_node.time = df_nodes['data_time'][i]
        geo_attr = analyze_geojson(df_nodes['geojson'][i])
        pheno_node.geo_attr = geo_attr
        pheno_node.value = df_nodes['max_value'][i]
        pheno_list.append(pheno_node)
    return pheno_list
