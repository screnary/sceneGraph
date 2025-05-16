# main.py
import os
import numpy as np
from graph import Node, Edge, SceneGraph
from calculators import (
    EdgeWeightCalculator, 
    CompatibilityWeightCalculator, 
    DistanceWeightCalculator, 
    CompositeWeightCalculator
)

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

if __name__ == "__main__":
    run_example()
