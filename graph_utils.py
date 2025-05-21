# graph_utils.py
import json
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import copy

class Node:
    """
    基础节点类，用于定义装备或环境节点。
    """
    def __init__(self, node_id, node_type, attributes):
        """
        初始化节点
        :param node_id: 节点的唯一标识符
        :param node_type: 节点类型（例如 'Equipment' 或 'Environment'）
        :param attributes: 节点的属性（字典形式）
        """
        self.node_id = node_id
        self.node_type = node_type
        self.attributes = attributes
    
    def update_attribute(self, updates):
        """
        同时更新节点的多个属性值。
        :param updates: 字典或列表，包含要更新的属性路径和新值
                        如果是字典：{attribute_path: new_value}，其中attribute_path可以是元组或列表形式的路径
                        如果是列表：[(attribute_path, new_value)]
        
        示例:
            update_attribute({('Value', 'Temperature'): 25, ('Value', 'Humidity'): 85})
            update_attribute([(('Value', 'Temperature'), 25), (('Value', 'Humidity'), 85)])
        """
        if isinstance(updates, dict):
            update_items = updates.items()
        elif isinstance(updates, list):
            update_items = updates
        else:
            raise TypeError("Updates must be a dictionary or a list of (path, value) tuples")
        
        for path, value in update_items:
            # 确保路径是元组或列表
            if isinstance(path, str):
                path = [path]
            
            current = self.attributes
            # 便利路径中，除最后一个键之外的所有键，确保路径存在
            for key in path[:-1]:
                if key not in current:
                    # raise KeyError(f"Key '{key}' not found in attributes.")
                    current[key] = {}
                current = current[key]
            
            final_key = path[-1]
            # if final_key not in current:
            #     raise KeyError(f"Key '{final_key}' not found in attributes.")
            current[final_key] = value
    
    # 保留原有方法以保持向后兼容性
    def update_single_attribute(self, attribute_path, new_value):
        """
        更新节点的单个属性值（向后兼容）。
        :param attribute_path: 属性的路径（支持嵌套字典，例如 ['Value', 'Temperature']）
        :param new_value: 新的属性值
        """
        self.update_attribute({tuple(attribute_path): new_value})

    def __repr__(self):
        return f"Node(ID={self.node_id}, Type={self.node_type}, Attributes={self.attributes})"


class Edge:
    """
    边类，用于定义节点之间的关系。
    """
    def __init__(self, source_node, target_node, edge_type, attributes=None):
        """
        初始化边
        :param source_node: 起始节点
        :param target_node: 目标节点
        :param edge_type: 边的类型（例如 'Compatible', 'NotCompatible'）
        :param attributes: 边的属性（字典形式）
        """
        self.source_node = source_node
        self.target_node = target_node
        self.edge_type = edge_type
        self.attributes = attributes or {}
        self.weight = 0  # 初始权值为0

    def set_weight(self, weight):
        """
        设置边的权值
        :param weight: 权值
        """
        self.weight = weight

    def __repr__(self):
        return (f"Edge(Source={self.source_node.node_id}, Target={self.target_node.node_id}, "
                f"Type={self.edge_type}, Weight={self.weight:.2f}, Attributes={self.attributes})")


class SceneGraph:
    """
    场景图类，用于管理节点和边。
    """
    def __init__(self):
        """
        初始化场景图
        """
        self.nodes = {}  # 存储节点，键为节点ID
        self.edges = []  # 存储边
        self.weight_calculator = None  # 默认无权值计算器
    
    def add_node(self, node):
        """
        添加节点到场景图
        :param node: Node 对象
        """
        if node.node_id in self.nodes:
            raise ValueError(f"Node with ID {node.node_id} already exists.")
        self.nodes[node.node_id] = node

    def add_edge(self, edge):
        """
        添加边到场景图
        :param edge: Edge 对象
        """
        self.edges.append(edge)
    
    def set_weight_calculator(self, calculator):
        """
        设置边权值计算器
        :param calculator: EdgeWeightCalculator实例
        """
        self.weight_calculator = calculator
    
    def calculate_edge_weights(self):
        """
        计算所有边的权值
        :return: 更新后的边列表
        """
        if not self.weight_calculator:
            print("警告：未设置权值计算器，无法计算边权值")
            return self.edges
        
        for edge in self.edges:
            weight = self.weight_calculator.calculate(edge, self)
            edge.set_weight(weight)
        
        return self.edges

    def get_node(self, node_id):
        """
        根据ID获取节点
        
        :param node_id: 节点ID
        :return: 节点对象或None（如果不存在）
        """
        return self.nodes.get(node_id)
    
    def get_edges_to_node(self, node_id):
        """
        获取连接到指定节点的所有边
        
        :param node_id: 目标节点ID
        :return: 边列表
        """
        return [edge for edge in self.edges if edge.target_node.node_id == node_id]
    
    def get_edges_from_node(self, node_id):
        """
        获取从指定节点出发的所有边
        
        :param node_id: 源节点ID
        :return: 边列表
        """
        return [edge for edge in self.edges if edge.source_node.node_id == node_id]
    
    def get_connected_nodes(self, node_id):
        """
        获取与指定节点直接相连的所有节点
        
        :param node_id: 节点ID
        :return: 节点ID列表
        """
        connected_ids = []
        
        # 获取所有目标节点
        for edge in self.get_edges_from_node(node_id):
            connected_ids.append(edge.target_node.node_id)
        
        # 获取所有源节点
        for edge in self.get_edges_to_node(node_id):
            connected_ids.append(edge.source_node.node_id)
        
        # 去除重复
        return list(set(connected_ids))
    
    def remove_edge(self, edge):
        """
        从场景图中删除一条边
        
        :param edge: 要删除的边对象
        :return: 是否成功删除
        """
        if edge in self.edges:
            self.edges.remove(edge)
            return True
        return False
    
    def remove_edges_by_weight(self, condition="equal", threshold=0.0):
        """
        根据权重条件删除边
        
        :param condition: 条件类型，可以是 "equal", "less", "less_equal", "greater", "greater_equal"
        :param threshold: 阈值
        :return: 已删除的边数量
        """
        edges_to_remove = []
        removed_count = 0
        
        for edge in self.edges:
            remove = False
            
            if condition == "equal" and edge.weight == threshold:
                remove = True
            elif condition == "less" and edge.weight < threshold:
                remove = True
            elif condition == "less_equal" and edge.weight <= threshold:
                remove = True
            elif condition == "greater" and edge.weight > threshold:
                remove = True
            elif condition == "greater_equal" and edge.weight >= threshold:
                remove = True
            
            if remove:
                edges_to_remove.append(edge)
        
        # 删除收集到的边
        for edge in edges_to_remove:
            self.edges.remove(edge)
            removed_count += 1
        
        return removed_count
    
    def filter_edges(self, filter_function):
        """
        根据自定义过滤函数过滤边
        
        :param filter_function: 一个接收边作为参数并返回布尔值的函数，返回True的边会被保留
        :return: 已删除的边数量

        USAGE:
        def complex_filter(edge):
            # 组合多个条件
            # 保留权重大于0.4的兼容边或者权重大于0.7的任何边
            return (edge.edge_type == "Compatible" and edge.weight > 0.4) or edge.weight > 0.7

        graph.filter_edges(complex_filter)
        """
        filtered_edges = [edge for edge in self.edges if filter_function(edge)]
        return filtered_edges
    
    def extract_subgraph(self, min_weight=0.0, max_weight=float('inf'), edge_types=None):
        """
        根据边权值和类型提取子图
        :param min_weight: 最小边权值，低于此值的边将被排除
        :param max_weight: 最大边权值，高于此值的边将被排除
        :param edge_types: 要包含的边类型列表，None表示所有类型
        :return: 新的SceneGraph实例，包含满足条件的节点和边
        """
        # 确保边权值已计算
        if self.weight_calculator:
            self.calculate_edge_weights()
        
        # 创建新的子图
        subgraph = SceneGraph()

        # 定义过滤条件
        def edge_filter(edge):
            # 检查边权值范围
            if edge.weight < min_weight or edge.weight > max_weight:
                return False
            
            # 检查边类型
            if edge_types and edge.edge_type not in edge_types:
                return False
                
            return True

        # 使用filter_edges获取满足条件的边
        filtered_edges = self.filter_edges(edge_filter)

        # 收集需要包含的节点
        included_nodes = set()
        for edge in filtered_edges:
            included_nodes.add(edge.source_node.node_id)
            included_nodes.add(edge.target_node.node_id)
        
        # 添加节点到子图
        for node_id in included_nodes:
            subgraph.add_node(self.nodes[node_id])
        
        # 添加边到子图
        for edge in filtered_edges:
            subgraph.add_edge(edge)
        
        # 复制权值计算器
        subgraph.weight_calculator = self.weight_calculator
        
        return subgraph
    
    def check_compatibility(self, equipment_node, environment_node):
        """
        检查设备和环境节点之间的兼容性
        :param equipment_node: 设备节点
        :param environment_node: 环境节点
        :return: (bool, str) 兼容性结果和原因
        """
        supported_env = equipment_node.attributes.get("Supported_Environment", {})
        env_params = environment_node.attributes.get("Value", {})
        
        not_compatible = False
        reason = ""
        
        for param, value in env_params.items():
            if param in supported_env:
                min_val, max_val = supported_env[param]
                if not (min_val <= value <= max_val):
                    not_compatible = True
                    reason += f"{param} ({value}) exceeds range [{min_val}, {max_val}]. "
        
        return not_compatible, reason

    def initialize_edges(self):
        """
        遍历所有节点，根据规则初始化装备和环境节点之间的边。
        仅在环境参数超出设备适应范围时创建 NotCompatible 类型的边。
        """
        for source_id, source_node in self.nodes.items():
            # 只处理装备节点
            if source_node.node_type != "Equipment":
                continue

            for target_id, target_node in self.nodes.items():
                # 只处理环境节点
                if target_node.node_type != "Environment":
                    continue

                # 检查兼容性
                not_compatible, reason = self.check_compatibility(source_node, target_node)

                # 如果发现不兼容的情况，创建 NotCompatible 边
                if not_compatible:
                    edge = Edge(source_node, target_node, "NotCompatible", {"Reason": reason})
                    self.add_edge(edge)
    
    def update_relationship(self):
        """
        根据规则动态更新边的关系（适配或不适配）。
        如果边的类型被置为 None，则从场景图中移除该边。
        """
        # 使用列表推导式更新边集合
        updated_edges = []
        
        # 检查所有可能的设备-环境节点对
        equipment_nodes = [node for node in self.nodes.values() if node.node_type == "Equipment"]
        environment_nodes = [node for node in self.nodes.values() if node.node_type == "Environment"]
        
        for equip_node in equipment_nodes:
            for env_node in environment_nodes:
                not_compatible, reason = self.check_compatibility(equip_node, env_node)
                
                if not_compatible:
                    # 检查是否已存在此边
                    existing_edge = None
                    for edge in self.edges:
                        if (edge.source_node == equip_node and edge.target_node == env_node and 
                            edge.edge_type == "NotCompatible"):
                            existing_edge = edge
                            break
                    
                    if existing_edge:
                        # 更新已有边的属性
                        existing_edge.attributes["Reason"] = reason
                        updated_edges.append(existing_edge)
                    else:
                        # 创建新边
                        new_edge = Edge(equip_node, env_node, "NotCompatible", {"Reason": reason})
                        updated_edges.append(new_edge)
        
        # 更新边集合
        self.edges = updated_edges

    def __repr__(self):
        return f"SceneGraph(Nodes={list(self.nodes.values())}, Edges={self.edges})"


"""
functions using to construct graph
"""
def build_equipment_environment_edges(scene_graph):
    """
    自动构建 Equipment 和 Environment 节点之间的边
    根据设备的支持环境参数和环境节点的当前值确定兼容性
    仅创建不兼容边

    :param scene_graph: SceneGraph 对象
    :return: 创建的边列表
    """
    created_edges = []
    
    # 获取所有设备节点
    equipment_nodes = [node for node_id, node in scene_graph.nodes.items() 
                      if node.node_type == "Equipment"]
    
    # 获取所有环境节点
    environment_nodes = [node for node_id, node in scene_graph.nodes.items() 
                        if node.node_type == "Environment"]
    
    print(f"找到 {len(equipment_nodes)} 个设备节点和 {len(environment_nodes)} 个环境节点")
    
    # 遍历所有设备-环境节点对
    for equip_node in equipment_nodes:
        # 获取设备支持的环境参数
        supported_env = equip_node.attributes.get("Supported_Environment", {})
        if not supported_env:
            print(f"设备节点 {equip_node.node_id} 没有定义支持的环境参数，跳过")
            continue  # 跳过没有支持环境参数的设备
        
        for env_node in environment_nodes:
            # 获取环境的当前参数值
            env_params = env_node.attributes.get("Value", {})
            if not env_params:
                print(f"环境节点 {env_node.node_id} 没有定义环境参数值，跳过")
                continue  # 跳过没有环境参数的节点
            
            # 检查兼容性
            not_compatible = False
            reason = ""
            
            # 检查环境节点的类型是否在设备支持的环境参数中
            compatible_params = 0
            for env_type, value in env_params.items():
                if env_type in supported_env:
                    compatible_params += 1
                    min_val, max_val = supported_env[env_type]
                    if not (min_val <= value <= max_val):
                        not_compatible = True
                        reason += f"{env_type} ({value}) 超出范围 [{min_val}, {max_val}]。 "
            
            # 只有当环境类型存在于设备支持的环境参数中时才创建边
            if compatible_params > 0:
                # 根据兼容性创建边
                if not_compatible:
                    edge = Edge(equip_node, env_node, "NotCompatible", {"Reason": reason})
                    print(f"创建不兼容边: {equip_node.node_id} -> {env_node.node_id}, 原因: {reason}")
                # else:
                #     edge = Edge(equip_node, env_node, "Compatible")
                #     print(f"创建兼容边: {equip_node.node_id} -> {env_node.node_id}")

                # 添加到场景图
                scene_graph.add_edge(edge)
                created_edges.append(edge)
    
    return created_edges


def load_trajectory_from_json(json_file):
    """
    从JSON文件加载轨迹数据
    
    :param json_file: JSON文件路径
    :return: 包含轨迹数据的DataFrame
    """
    try:
        with open(json_file, 'r') as f:
            data = json.load(f)
        
        # 提取线特征（整体轨迹）属性
        line_feature = next((f for f in data['features'] if f['geometry']['type'] == 'LineString'), None)
        if not line_feature:
            raise ValueError("无法找到LineString特征")
        
        # 提取点特征并转换为DataFrame
        point_features = [f for f in data['features'] if f['geometry']['type'] == 'Point']
        
        if not point_features:
            raise ValueError("无法找到Point特征")
        
        trajectory_data = []
        
        for feature in point_features:
            coords = feature['geometry']['coordinates']
            props = feature['properties']
            
            # 提取时间戳
            timestamp = props.get('timestamp')
            if timestamp:
                try:
                    timestamp = pd.to_datetime(timestamp)
                except:
                    # 如果无法解析时间戳，保留原始字符串
                    pass
            
            # 构建数据点
            point_data = {
                'longitude': coords[0],
                'latitude': coords[1],
                'timestamp': timestamp,
                'speed_knots': props.get('speed_knots', 0),
                'heading': props.get('heading', 0),
                'cumulative_distance_km': props.get('distance_km', 0)
            }
            
            trajectory_data.append(point_data)
        
        # 创建DataFrame并按时间戳排序
        df = pd.DataFrame(trajectory_data)
        if 'timestamp' in df.columns and df['timestamp'].dtype != 'object':
            df = df.sort_values('timestamp')
        
        return df
    
    except Exception as e:
        print(f"加载轨迹数据失败: {e}")
        raise


# 动态更新图函数
def update_graph_with_trajectory(graph, trajectory_point, ship_node_id="ship_001"):
    """
    根据轨迹点更新图
    
    :param graph: SceneGraph对象
    :param trajectory_point: 轨迹点（Series或dict）
    :param ship_node_id: 船舶节点ID
    :return: 更新后的图
    """
    # 获取船舶节点
    ship_node = graph.get_node(ship_node_id)
    if not ship_node:
        print(f"错误：找不到ID为{ship_node_id}的船舶节点")
        return graph
    
    # 更新船舶位置
    lon = trajectory_point['longitude']
    lat = trajectory_point['latitude']
    ship_node.update_attribute({
        'Location': f"{lon:.6f}, {lat:.6f}"
    })
    
    # 如果有速度信息，更新
    if 'speed_knots' in trajectory_point:
        speed = trajectory_point['speed_knots']
        ship_node.update_attribute({
            ('Value', 'Speed'): f"{speed:.2f} knots"
        })
    
    # 如果有航向信息，更新
    if 'heading' in trajectory_point:
        heading = trajectory_point['heading']
        ship_node.update_attribute({
            ('Value', 'Heading'): f"{heading:.1f}°"
        })
    
    # 重新计算所有边的权值
    graph.calculate_edge_weights()
    
    # 移除权值为0的边
    graph.remove_edges_by_weight(condition="equal", threshold=0.0)
    
    return graph


# 动态更新图函数
def update_graph_with_trajectory(graph, trajectory_point, ship_node_id="ship_001"):
    """
    根据轨迹点更新图
    
    :param graph: SceneGraph对象
    :param trajectory_point: 轨迹点（Series或dict）
    :param ship_node_id: 船舶节点ID
    :return: 更新后的图
    """
    # 获取船舶节点
    ship_node = graph.get_node(ship_node_id)
    if not ship_node:
        print(f"错误：找不到ID为{ship_node_id}的船舶节点")
        return graph
    
    # 更新船舶位置
    lon = trajectory_point['longitude']
    lat = trajectory_point['latitude']
    ship_node.update_attribute({
        'Location': f"{lon:.6f}, {lat:.6f}"
    })
    
    # 如果有速度信息，更新
    if 'speed_knots' in trajectory_point:
        speed = trajectory_point['speed_knots']
        ship_node.update_attribute({
            ('Value', 'Speed'): f"{speed:.2f} knots"
        })
    
    # 如果有航向信息，更新
    if 'heading' in trajectory_point:
        heading = trajectory_point['heading']
        ship_node.update_attribute({
            ('Value', 'Heading'): f"{heading:.1f}°"
        })
    
    # 重新计算所有边的权值
    graph.calculate_edge_weights()
    
    # 移除权值为0的边
    graph.remove_edges_by_weight(condition="equal", threshold=0.0)
    
    return graph


# 创建动态场景图序列
def create_dynamic_graph_series(trajectory_df, base_graph, ship_node_id="ship_001", interval_minutes=60, max_graphs=10):
    """
    根据轨迹创建一系列随时间变化的场景图
    
    :param trajectory_df: 轨迹DataFrame
    :param base_graph: 基础SceneGraph对象
    :param ship_node_id: 船舶节点ID
    :param interval_minutes: 图之间的时间间隔(分钟)
    :param max_graphs: 最大图数量
    :return: (graph_series, timestamps) 元组，图序列和对应的时间戳
    """
    # 确保时间戳是datetime类型并排序
    if 'timestamp' in trajectory_df.columns:
        if trajectory_df['timestamp'].dtype == 'object':
            try:
                trajectory_df['timestamp'] = pd.to_datetime(trajectory_df['timestamp'])
            except:
                print("警告: 无法将时间戳转换为datetime类型")
        trajectory_df = trajectory_df.sort_values('timestamp')
    
    # 计算需要采样的时间点
    if 'timestamp' in trajectory_df.columns and pd.api.types.is_datetime64_any_dtype(trajectory_df['timestamp']):
        start_time = trajectory_df['timestamp'].iloc[0]
        end_time = trajectory_df['timestamp'].iloc[-1]
        
        # 计算总时间跨度(分钟)
        try:
            total_minutes = (end_time - start_time).total_seconds() / 60
        except:
            # 处理numpy datetime
            total_minutes = (end_time - start_time) / np.timedelta64(1, 'm')
        
        # 调整间隔以确保不超过最大图数量
        if total_minutes / interval_minutes > max_graphs:
            interval_minutes = total_minutes / max_graphs
        
        # 生成采样时间点
        num_points = min(max_graphs, int(total_minutes / interval_minutes) + 1)
        sample_times = []
        indices = []
        
        for i in range(num_points):
            try:
                # 标准datetime
                offset = timedelta(minutes=i * interval_minutes)
                current_time = start_time + offset
                sample_times.append(current_time)
                
                # 找到最接近的时间点索引
                trajectory_df['time_diff'] = abs(trajectory_df['timestamp'] - current_time)
                closest_idx = trajectory_df['time_diff'].idxmin()
                indices.append(closest_idx)
                trajectory_df = trajectory_df.drop('time_diff', axis=1)
            except:
                # numpy datetime
                offset = np.timedelta64(int(i * interval_minutes), 'm')
                current_time = start_time + offset
                sample_times.append(current_time)
                
                # 找到最接近的时间点索引
                trajectory_df['time_diff'] = abs(trajectory_df['timestamp'] - current_time)
                closest_idx = trajectory_df['time_diff'].idxmin()
                indices.append(closest_idx)
                trajectory_df = trajectory_df.drop('time_diff', axis=1)
    else:
        # 如果没有有效的时间戳列，使用等间隔采样
        indices = np.linspace(0, len(trajectory_df)-1, min(max_graphs, len(trajectory_df)))
        indices = [int(i) for i in indices]
        sample_times = [f"点 {i+1}" for i in range(len(indices))]
        
    # 创建图序列
    graph_series = []
    timestamps = []
    
    for i, (sample_time, idx) in enumerate(zip(sample_times, indices)):
        if isinstance(sample_time, (datetime, pd.Timestamp, np.datetime64)):
            # 格式化时间戳显示
            if isinstance(sample_time, datetime):
                timestamp_str = sample_time.strftime("%Y-%m-%d %H:%M")
            else:
                timestamp_str = pd.to_datetime(sample_time).strftime("%Y-%m-%d %H:%M")
        else:
            timestamp_str = sample_time
        
        # 获取轨迹点
        trajectory_point = trajectory_df.iloc[idx]
        
        # 创建当前时间点的图（复制基础图）
        current_graph = copy_graph(base_graph)
        
        # 更新图
        current_graph = update_graph_with_trajectory(
            current_graph, 
            trajectory_point,
            ship_node_id=ship_node_id
        )
        
        graph_series.append(current_graph)
        timestamps.append(timestamp_str)
    
    return graph_series, timestamps

def copy_graph(graph):
    """
    深度复制场景图
    
    :param graph: 原始SceneGraph对象
    :return: 复制后的SceneGraph对象
    """
    
    # 创建新图
    new_graph = SceneGraph()
    
    # 复制节点
    for node_id, node in graph.nodes.items():
        # 深度复制节点属性
        attributes_copy = copy.deepcopy(node.attributes)
        new_node = Node(node.node_id, node.node_type, attributes_copy)
        new_graph.add_node(new_node)
    
    # 复制边
    for edge in graph.edges:
        source_node = new_graph.get_node(edge.source_node.node_id)
        target_node = new_graph.get_node(edge.target_node.node_id)
        
        # 深度复制边属性
        attributes_copy = copy.deepcopy(edge.attributes)
        new_edge = Edge(source_node, target_node, edge.edge_type, attributes_copy)
        new_edge.set_weight(edge.weight)
        new_graph.add_edge(new_edge)
    
    # 复制权值计算器
    if graph.weight_calculator:
        new_graph.weight_calculator = graph.weight_calculator
    
    return new_graph
