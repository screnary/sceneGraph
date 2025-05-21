# main.py
import os
import sys
import numpy as np
import parse_tools as pt
from graph_utils import Node, Edge, SceneGraph
import graph_utils as GU
from datetime import datetime, timedelta
from calculators import (
    EdgeWeightCalculator, 
    CompatibilityWeightCalculator, 
    DistanceWeightCalculator,
    GeoDistanceWeightCalculator,
    CompositeWeightCalculator
)
from visualizer import visualize_scene_graph, visualize_network_graph, quick_view, visualize_network_graph_plotly, visualize_dynamic_network

import pdb

def run_example():
    """运行示例代码，展示系统功能"""
    # 初始化场景图
    graph = SceneGraph()

    # 添加装备节点
    sensor = Node(
        node_id="Sensor_01",
        node_type="Equipment",
        attributes={
            "Name": "温湿度传感器",
            "Function": "环境监测",
            "Status": "在线",
            "Location": "23.5, 45.2",
            "Supported_Environment": {
                "Temperature": [0, 50],
                "Humidity": [10, 90]
            }
        }
    )
    graph.add_node(sensor)

    # 添加另一个装备节点
    sensor2 = Node(
        node_id="Sensor_02",
        node_type="Equipment",
        attributes={
            "Name": "高温传感器",
            "Function": "环境监测",
            "Status": "在线",
            "Location": "24.0, 46.0",
            "Supported_Environment": {
                "Temperature": [30, 100],
                "Humidity": [5, 60]
            }
        }
    )
    graph.add_node(sensor2)

    # 添加环境节点
    temperature = Node(
        node_id="Temperature",
        node_type="Environment",
        attributes={
            "Name": "温度",
            "Type": "Climate",
            "Value": {
                "Temperature": 45  # 在第一个传感器范围内，接近上限
            },
            "Location": "23.5, 45.3"
        }
    )
    humidity = Node(
        node_id="Humidity",
        node_type="Environment",
        attributes={
            "Name": "湿度",
            "Type": "Climate",
            "Value": {
                "Humidity": 75  # 在第一个传感器范围内，在中间偏上
            },
            "Location": "23.6, 45.5"
        }
    )
    graph.add_node(temperature)
    graph.add_node(humidity)

    # 手动创建边
    edge1 = Edge(sensor, temperature, "Compatible")
    edge2 = Edge(sensor, humidity, "Compatible")
    edge3 = Edge(sensor2, temperature, "Compatible")
    edge4 = Edge(sensor2, humidity, "NotCompatible")  # 超出湿度支持范围
    
    graph.add_edge(edge1)
    graph.add_edge(edge2)
    graph.add_edge(edge3)
    graph.add_edge(edge4)

    # 创建组合权值计算器
    composite_calculator = CompositeWeightCalculator()
    
    # 添加兼容性计算器
    composite_calculator.add_calculator(CompatibilityWeightCalculator(), weight=0.7)
    
    # 添加距离计算器
    composite_calculator.add_calculator(DistanceWeightCalculator(), weight=0.3)
    
    # 设置场景图的权值计算器
    graph.set_weight_calculator(composite_calculator)
    
    # 计算所有边的权值
    graph.calculate_edge_weights()
    
    print("计算权值后的场景图：")
    for edge in graph.edges:
        print(edge)
    
    # 提取权值大于0.5的子图
    subgraph = graph.extract_subgraph(min_weight=0.5)
    
    print("\n权值大于0.5的子图：")
    for edge in subgraph.edges:
        print(edge)
    
    # 按照边类型筛选
    compatible_subgraph = graph.extract_subgraph(edge_types=["Compatible"])
    
    print("\n只包含Compatible边的子图：")
    for edge in compatible_subgraph.edges:
        print(edge)
    
    # 示例：更新节点属性并查看权值变化
    print("\n更新节点属性后的权值变化：")
    # 更新温度值
    temperature.update_attribute({('Value', 'Temperature'): 35})  # 更适合两个传感器
    
    # 重新计算权值
    graph.calculate_edge_weights()
    
    for edge in graph.edges:
        if edge.source_node.node_id == "Sensor_01" and edge.target_node.node_id == "Temperature":
            print(f"Sensor_01 → Temperature 权值: {edge.weight:.2f}")
        elif edge.source_node.node_id == "Sensor_02" and edge.target_node.node_id == "Temperature":
            print(f"Sensor_02 → Temperature 权值: {edge.weight:.2f}")

def run_example_2(debug=False):
    # 初始化场景图
    graph = SceneGraph()

    # 添加装备节点
    #TODO： load from json file
    ship = Node(
        node_id="ship_001",
        node_type="Equipment",
        attributes={
            "Name": "运输船",
            "Function": "运输",
            "Status": "在线",
            "Location": "122.382, 25.765",
            "Supported_Environment": {
                "锋面": [0, 0.06],
                "风暴增水": [0, 3],
                "中尺度涡": [0, 5]
            }
        }
    )
    graph.add_node(ship)

    # 添加环境节点
    data_root = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),'data')
    data_path = os.path.join(data_root, 'warning_info.xls')

    env_list = pt.parse_xls(data_path)  # len==64
    # print(env_list)
    # pdb.set_trace()
    for i,env_instance in enumerate(env_list):
        bounds = env_instance.geo_attr.bounds
        center_x = (bounds.min_lon + bounds.max_lon) / 2
        center_y = (bounds.min_lat + bounds.max_lat) / 2
        node_tmp = Node(
            node_id="{}_{:03d}".format(env_instance.type, i+1),
            node_type="Environment",
            attributes={
                "Name": env_instance.type,
                "Value": {
                    env_instance.type: env_instance.value  # 在第一个传感器范围内，在中间偏上
                },
                "Location": "{:.6f}, {:.6f}".format(center_x, center_y),
                "bounds": bounds
            }
        )
        graph.add_node(node_tmp)
    
    created_edges = GU.build_equipment_environment_edges(graph)  # graph utility

    # 创建组合权值计算器
    composite_calculator = CompositeWeightCalculator()

    # create filter calculator
    filter_calculator = GeoDistanceWeightCalculator(max_distance=150)
    composite_calculator.set_filter(filter_calculator, threshold=0.0, mode="equal")
    
    # 添加兼容性计算器
    composite_calculator.add_calculator(CompatibilityWeightCalculator(), weight=0.6)
    
    # 添加距离计算器
    composite_calculator.add_calculator(GeoDistanceWeightCalculator(max_distance=60), weight=0.4)
    
    # 设置场景图的权值计算器
    graph.set_weight_calculator(composite_calculator)
    
    # 计算所有边的权值
    graph.calculate_edge_weights()
    # graph.remove_edges_by_weight(condition="equal", threshold=0.0)

    # 查看图节点、边权值结果
    if debug:
        filtered_count = sum(1 for edge in graph.edges if edge.weight == 0 and edge.edge_type == "NotCompatible")
        non_zero_count = sum(1 for edge in graph.edges if edge.weight > 0 and edge.edge_type == "NotCompatible")

        print(f"\n权重过滤结果:")
        print(f"  被过滤掉的边数量: {filtered_count}")
        print(f"  保留的边数量: {non_zero_count}")

        if non_zero_count > 0:
            non_zero_weights = [edge.weight for edge in graph.edges 
                                if edge.weight > 0 and edge.edge_type == "NotCompatible"]
            print(f"  保留边的平均权重: {sum(non_zero_weights) / len(non_zero_weights):.2f}")
            print(f"  保留边的最大权重: {max(non_zero_weights):.2f}")
            print(f"  保留边的最小权重: {min(non_zero_weights):.2f}")
    
    current_time = datetime.now()

    # launch_viewer(graph, center_coordinate="122.382, 25.765")  # QT界面效果较差，效率很低 相当于C嵌B；可以先不使用这个界面了；主要是做出来“动态更新”的算法服务
    # GU.visualize_scene_graph(graph, filename="../results/ocean_environment_map_{}.html".format(current_time), center_coordinate="122.382, 25.765", filter_min_weight=0.01)

    # 加载轨迹数据，并根据轨迹数据构建动态更新的Graph
    trajectory_df = GU.load_trajectory_from_json("../data/example_trajectory.geojson")
    # 创建动态图序列
    # 每60分钟一个图
    # graph_series, timestamps = GU.create_dynamic_graph_series(trajectory_df, graph, ship_node_id="ship_001",
    #                                                           interval_minutes=60, max_graphs=20)
    # visualize_dynamic_network(graph_series, timestamps=timestamps, 
    #                           filename="../results/trajectory_network_animation_{}.html".format(current_time), 
    #                           filter_min_weight=0.01)
    
    # visualize_scene_graph(graph, filename="../results/ocean_environment_static_map_{}.html".format(current_time), 
    #                       center_coordinate="122.382, 25.765", filter_min_weight=0.01)
    
    _, graph_series, timestamps = visualize_scene_graph(graph, filename="../results/ocean_environment_animated_map_{}.html".format(current_time), 
                          center_coordinate="122.382, 25.765", filter_min_weight=0.01, draw_bounds=False,
                          trajectory_df=trajectory_df, animate=True, time_interval=500, ship_node_id="ship_001")
    
    # using graph series from visualize_scene_graph, to visualize_dynamic_network
    visualize_dynamic_network(graph_series, timestamps=timestamps, 
                              filename="../results/trajectory_network_animation_{}.html".format(current_time), 
                              filter_min_weight=0.01)


if __name__ == "__main__":
    run_example_2(debug=True)
