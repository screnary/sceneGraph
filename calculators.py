# calculators.py

class EdgeWeightCalculator:
    """
    边权值计算器基类，提供计算边权值的接口和基础实现
    """
    def calculate(self, edge, scene_graph=None):
        """
        计算边的权值
        :param edge: 要计算权值的边
        :param scene_graph: 可选，提供场景图上下文供计算使用
        :return: 计算的权值
        """
        raise NotImplementedError("子类必须实现该方法")
    
    def recalculate_all_weights(self, scene_graph):
        """
        重新计算场景图中所有边的权值
        :param scene_graph: 场景图
        :return: 包含边和权值的字典 {edge: weight}
        """
        weights = {}
        for edge in scene_graph.edges:
            weights[edge] = self.calculate(edge, scene_graph)
        return weights


class CompatibilityWeightCalculator(EdgeWeightCalculator):
    """
    基于兼容性计算边权值的实现
    """
    def calculate(self, edge, scene_graph=None):
        """
        根据环境参数与设备支持范围的兼容性计算权值
        兼容性越高，权值越大；不兼容时权值为负数
        :param edge: 要计算权值的边
        :param scene_graph: 可选参数，此实现不需要
        :return: 权值，范围从-1到1
        """
        # 检查是否为设备-环境关系边
        if edge.source_node.node_type != "Equipment" or edge.target_node.node_type != "Environment":
            return 0  # 非设备-环境关系边，权值为0
        
        # 获取设备支持的环境参数范围
        supported_env = edge.source_node.attributes.get("Supported_Environment", {})
        # 获取实际环境参数值
        env_params = edge.target_node.attributes.get("Value", {})
        
        # 如果没有环境参数或支持范围，返回0
        if not supported_env or not env_params:
            return 0
        
        # 计算所有参数的兼容性得分总和，并取平均值
        total_score = 0
        param_count = 0
        
        for param, value in env_params.items():
            if param in supported_env:
                min_val, max_val = supported_env[param]
                param_range = max_val - min_val
                
                # 避免除以零
                if param_range == 0:
                    continue
                
                # 计算参数值在支持范围内的位置（0表示最小值，1表示最大值）
                if value < min_val:
                    # 低于最小值，给予负分
                    normalized_distance = (min_val - value) / param_range
                    score = -min(normalized_distance, 1)  # 限制在-1范围内
                elif value > max_val:
                    # 高于最大值，给予负分
                    normalized_distance = (value - max_val) / param_range
                    score = -min(normalized_distance, 1)  # 限制在-1范围内
                else:
                    # 在范围内，计算距离中心点的距离（中心点得分最高为1）
                    midpoint = (min_val + max_val) / 2
                    # 将范围内的值映射到0-1，越接近中点值越高
                    score = 1 - 2 * abs(value - midpoint) / param_range
                
                total_score += score
                param_count += 1
        
        # 计算平均得分
        if param_count > 0:
            return total_score / param_count
        return 0


class DistanceWeightCalculator(EdgeWeightCalculator):
    """
    基于节点间物理距离计算边权值的实现
    """
    def calculate(self, edge, scene_graph=None):
        """
        根据节点的位置计算物理距离，距离越近权值越高
        :param edge: 要计算权值的边
        :param scene_graph: 可选参数，此实现不需要
        :return: 权值，范围从0到1（1表示距离为0，0表示距离无限远）
        """
        # 获取源节点和目标节点的位置
        source_location = edge.source_node.attributes.get("Location")
        target_location = edge.target_node.attributes.get("Location")
        
        # 如果任一节点没有位置信息，返回默认值
        if not source_location or not target_location:
            return 0.5  # 默认中等权值
        
        # 解析位置信息（假设格式为"x, y"）
        try:
            source_x, source_y = map(float, source_location.split(","))
            target_x, target_y = map(float, target_location.split(","))
            
            # 计算欧几里德距离
            distance = ((source_x - target_x) ** 2 + (source_y - target_y) ** 2) ** 0.5
            
            # 将距离转换为权值，使用反比例函数
            # 距离为0时权值为1，距离越大权值越接近0
            # 使用参数调整衰减速率
            decay_factor = 0.1  # 可调整的衰减因子
            weight = 1 / (1 + decay_factor * distance)
            
            return weight
        except (ValueError, TypeError):
            # 如果位置格式不正确，返回默认值
            return 0.5


class CompositeWeightCalculator(EdgeWeightCalculator):
    """
    组合多种权值计算方法，根据权重组合结果
    """
    def __init__(self):
        """初始化组合权值计算器"""
        self.calculators = []  # 存储(计算器, 权重)元组的列表
    
    def add_calculator(self, calculator, weight=1.0):
        """
        添加一个权值计算器及其权重
        :param calculator: EdgeWeightCalculator的实例
        :param weight: 该计算器结果的权重
        """
        self.calculators.append((calculator, weight))
    
    def calculate(self, edge, scene_graph=None):
        """
        组合多个计算器的结果
        :param edge: 要计算权值的边
        :param scene_graph: 场景图上下文
        :return: 组合计算的权值
        """
        if not self.calculators:
            return 0  # 没有计算器时返回0
        
        total_weight = 0
        weighted_sum = 0
        
        for calculator, weight in self.calculators:
            # 计算单个计算器的权值
            value = calculator.calculate(edge, scene_graph)
            # 累加加权和
            weighted_sum += value * weight
            total_weight += weight
        
        # 计算加权平均
        if total_weight > 0:
            return weighted_sum / total_weight
        return 0
