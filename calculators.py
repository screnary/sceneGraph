# calculators.py
import math
import re
from geopy.distance import geodesic

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
        :raises ValueError: 当环境参数值低于设备支持的最小值时抛出
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
        
        # 计算所有参数的权重
        total_weight = 0
        param_count = 0
        
        for env_type, value in env_params.items():
            if env_type in supported_env:
                min_val, max_val = supported_env[env_type]
                param_range = max_val - min_val
                
                # 避免除以零
                if param_range == 0:
                    continue
                
                # 检查参数是否在支持范围内
                if value < min_val:
                    # 低于最小值，抛出错误
                    raise ValueError(f"环境参数 {env_type} 的值 {value} 低于设备支持的最小值 {min_val}")
                elif value > max_val:
                    # 超出适用阈值上限，计算权重
                    # 超出程度越大，权重越大
                    # 使用非线性映射，确保权重在0到1之间并随超出程度增加
                    # 这里使用sigmoid函数变体，使得稍微超出时权重增长缓慢，大幅超出时权重接近1
                    excess_ratio = (value - max_val) / param_range  # 超出比例
                    weight = 1 - (1 / (1 + 0.5 * excess_ratio))  # 非线性映射到0-1
                    total_weight += weight
                    param_count += 1
                else:
                    # 在范围内，权重为0（表示没有超出）
                    weight = 0
                    total_weight += weight
                    param_count += 1
        
        # 计算平均权重
        if param_count > 0:
            return total_weight / param_count
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


def calculate_geo_distance(lon1, lat1, lon2, lat2):
    """
    计算两个地理坐标点之间的距离(km)
    使用Haversine公式
    
    :param lon1: 第一个点的经度
    :param lat1: 第一个点的纬度
    :param lon2: 第二个点的经度
    :param lat2: 第二个点的纬度
    :return: 距离，单位为千米
    """
    
    # 将经纬度转换为弧度
    lon1, lat1, lon2, lat2 = map(math.radians, [lon1, lat1, lon2, lat2])
    
    # Haversine公式
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    r = 6371  # 地球平均半径，单位为千米
    
    return c * r


class GeoDistanceWeightCalculator(EdgeWeightCalculator):
    """
    基于地理距离计算边权值的实现
    距离越近权值越高，权值范围0到1
    """
    def __init__(self, max_distance=1000.0):
        """
        初始化地理距离计算器
        
        :param max_distance: 最大考虑距离(km)，超过此距离权值为0
        """
        self.max_distance = max_distance
    
    def calculate(self, edge, scene_graph=None):
        """
        根据节点的地理位置计算距离，距离越近权值越高
        
        :param edge: 要计算权值的边
        :param scene_graph: 可选参数，此实现不需要
        :return: 权值，范围从0到1（1表示距离为0，0表示距离大于等于max_distance）
        """
        # 获取源节点和目标节点的位置
        source_location = edge.source_node.attributes.get("Location")
        target_location = edge.target_node.attributes.get("Location")
        
        # 如果任一节点没有位置信息，返回默认值
        if not source_location or not target_location:
            return 0.5  # 默认中等权值
        
        # 解析位置信息（格式为"x, y"，表示经度和纬度）
        try:
            source_lon, source_lat = map(float, re.findall(r"[-+]?\d*\.\d+|\d+", source_location))
            target_lon, target_lat = map(float, re.findall(r"[-+]?\d*\.\d+|\d+", target_location))
            
            # 计算地理距离（千米）
            # distance = calculate_geo_distance(source_lon, source_lat, target_lon, target_lat)
            distance = geodesic((source_lat, source_lon), (target_lat, target_lon)).kilometers
            # 将距离转换为权值，距离越近权值越大
            # 当距离为0时权值为1，当距离大于等于max_distance时权值为0
            if distance >= self.max_distance:
                return 0
            
            return 1 - (distance / self.max_distance)
            
        except (ValueError, TypeError) as e:
            print(f"位置格式解析错误: {e}")
            # 如果位置格式不正确，返回默认值
            return 0.5


class CompositeWeightCalculator(EdgeWeightCalculator):
    """
    组合多个权值计算器的复合计算器
    支持使用地理距离作为过滤器(并提供更灵活的过滤选项)
    """
    def __init__(self, filter_calculator=None, filter_threshold=0, filter_mode="equal"):
        """
        初始化增强的组合权值计算器
        
        :param filter_calculator: 用作过滤器的计算器
        :param filter_threshold: 过滤阈值
        :param filter_mode: 过滤模式，可选值：
                           "equal" - 当值等于阈值时过滤
                           "less" - 当值小于等于阈值时过滤
                           "greater" - 当值大于等于阈值时过滤
        """
        self.calculators = []  # [(calculator, weight), ...]
        self.filter_calculator = filter_calculator
        self.filter_threshold = filter_threshold
        self.filter_mode = filter_mode
    
    def add_calculator(self, calculator, weight=1.0):
        """
        添加一个权值计算器
        
        :param calculator: 权值计算器对象
        :param weight: 此计算器的权重
        """
        self.calculators.append((calculator, weight))
    
    def set_filter(self, calculator, threshold=0, mode="equal"):
        """
        设置过滤器
        
        :param calculator: 用作过滤器的计算器
        :param threshold: 过滤阈值
        :param mode: 过滤模式
        """
        self.filter_calculator = calculator
        self.filter_threshold = threshold
        self.filter_mode = mode
    
    def should_filter(self, filter_value):
        """
        根据过滤模式决定是否过滤
        
        :param filter_value: 过滤器计算出的值
        :return: 如果应该过滤则返回True
        """
        if self.filter_mode == "equal":
            return filter_value == self.filter_threshold
        elif self.filter_mode == "less":
            return filter_value <= self.filter_threshold
        elif self.filter_mode == "greater":
            return filter_value >= self.filter_threshold
        return False
    
    def calculate(self, edge, scene_graph=None):
        """
        使用所有添加的计算器计算权值的加权平均
        如果设置了过滤器，则先检查是否需要过滤
        
        :param edge: 要计算权值的边
        :param scene_graph: 场景图对象
        :return: 组合计算的权值
        """
        if not self.calculators:
            return 0
        
        # 如果设置了过滤器，先检查是否需要过滤
        if self.filter_calculator:
            filter_value = self.filter_calculator.calculate(edge, scene_graph)
            if self.should_filter(filter_value):
                # 过滤条件满足，返回0
                return 0
        
        # 计算加权平均
        total_weight = 0
        total_factor = 0
        
        for calculator, factor in self.calculators:
            # 避免重复计算过滤器的值
            if calculator is self.filter_calculator:
                weight = filter_value
            else:
                weight = calculator.calculate(edge, scene_graph)
            
            # 累加加权权值
            total_weight += weight * factor
            total_factor += factor
        
        # 返回加权平均
        if total_factor > 0:
            return total_weight / total_factor
        return 0
