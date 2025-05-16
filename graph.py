# graph.py
import os
import numpy as np

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
            for key in path[:-1]:
                if key not in current:
                    raise KeyError(f"Key '{key}' not found in attributes.")
                current = current[key]
            
            final_key = path[-1]
            if final_key not in current:
                raise KeyError(f"Key '{final_key}' not found in attributes.")
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

    def find_node(self, node_id):
        """
        根据节点ID查找节点
        :param node_id: 节点ID
        :return: Node 对象
        """
        return self.nodes.get(node_id)
    
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
    
    def extract_subgraph(self, min_weight=0.0, edge_types=None):
        """
        根据边权值和类型提取子图
        :param min_weight: 最小边权值，低于此值的边将被排除
        :param edge_types: 要包含的边类型列表，None表示所有类型
        :return: 新的SceneGraph实例，包含满足条件的节点和边
        """
        # 确保边权值已计算
        if self.weight_calculator:
            self.calculate_edge_weights()
        
        # 创建新的子图
        subgraph = SceneGraph()
        included_nodes = set()
        
        # 筛选满足条件的边
        for edge in self.edges:
            # 检查边权值和类型
            if edge.weight < min_weight:
                continue
            if edge_types and edge.edge_type not in edge_types:
                continue
            
            # 添加满足条件的边的源节点和目标节点
            source_id = edge.source_node.node_id
            target_id = edge.target_node.node_id
            
            if source_id not in included_nodes:
                subgraph.add_node(edge.source_node)
                included_nodes.add(source_id)
            
            if target_id not in included_nodes:
                subgraph.add_node(edge.target_node)
                included_nodes.add(target_id)
            
            # 添加边到子图
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
