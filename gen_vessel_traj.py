import numpy as np
import math
from datetime import datetime, timedelta
import pandas as pd
from geopy.distance import geodesic
import matplotlib.pyplot as plt
from scipy.interpolate import splprep, splev


def generate_vessel_trajectory(control_points, vessel_speed_knots, time_step_minutes=5, smooth_factor=0.01, 
                              interpolate_method='bezier', start_time=None, speed_variation=0.1, 
                              include_noise=True, noise_level=0.0001):
    """
    根据控制点序列和船舶航行速度生成平滑轨迹
    
    :param control_points: 控制点列表，每个点为 (经度, 纬度) 格式
    :param vessel_speed_knots: 船舶平均速度（单位：节）
    :param time_step_minutes: 轨迹点之间的时间间隔（分钟）
    :param smooth_factor: 平滑因子，值越小曲线越接近控制点
    :param interpolate_method: 插值方法，可选 'bezier'（贝塞尔曲线）或 'linear'（线性插值）
    :param start_time: 起始时间，如果为None则使用当前时间
    :param speed_variation: 速度变化范围（0-1之间），表示速度的随机波动幅度
    :param include_noise: 是否包含噪声（模拟GPS误差等）
    :param noise_level: 噪声级别（经纬度单位）
    :return: 包含时间、位置、速度等信息的DataFrame
    """
    # 验证输入参数
    if len(control_points) < 2:
        raise ValueError("至少需要提供两个控制点")
    
    # 设置起始时间
    if start_time is None:
        start_time = datetime.now()
    elif isinstance(start_time, str):
        try:
            start_time = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            raise ValueError("起始时间格式应为 'YYYY-MM-DD HH:MM:SS'")
    elif isinstance(start_time, (np.datetime64, pd.Timestamp)):
        start_time = pd.to_datetime(start_time).to_pydatetime()
    
    # 将节转换为每分钟移动的度数（简化计算，1节 ≈ 1.852 km/h）
    # 在赤道附近，1度经度或纬度约等于111公里
    knots_to_degrees_per_minute = vessel_speed_knots * 1.852 / 111 / 60
    
    # 转换控制点为numpy数组以便处理
    control_points = np.array(control_points)
    
    # 根据插值方法生成平滑路径
    if interpolate_method == 'bezier':
        # 使用样条插值创建平滑曲线
        if len(control_points) < 4:
            # 对于少于4个点，添加辅助点以确保生成平滑曲线
            while len(control_points) < 4:
                # 在现有点之间插入中点
                new_points = []
                for i in range(len(control_points) - 1):
                    new_points.append(control_points[i])
                    mid_point = (control_points[i] + control_points[i+1]) / 2
                    new_points.append(mid_point)
                new_points.append(control_points[-1])
                control_points = np.array(new_points)
        
        # 使用B样条创建平滑曲线
        tck, u = splprep([control_points[:, 0], control_points[:, 1]], s=smooth_factor, k=min(3, len(control_points)-1))
        
        # 计算路径总长度（粗略估计）以确定插值点数量
        total_distance = 0
        for i in range(len(control_points) - 1):
            point1 = (control_points[i][1], control_points[i][0])  # 纬度, 经度
            point2 = (control_points[i+1][1], control_points[i+1][0])  # 纬度, 经度
            total_distance += geodesic(point1, point2).kilometers
        
        # 根据速度和时间步长估算需要的点数
        # 1节 ≈ 1.852 km/h，time_step_minutes分钟内的距离
        distance_per_step = vessel_speed_knots * 1.852 * (time_step_minutes / 60)
        num_points = max(100, int(total_distance / distance_per_step))
        
        # 创建均匀的参数值
        u_new = np.linspace(0, 1, num_points)
        
        # 计算平滑路径点
        smooth_points = np.column_stack(splev(u_new, tck))
        
    elif interpolate_method == 'linear':
        # 线性插值，并根据每段之间的距离按比例分配点
        smooth_points = []
        segment_counts = []
        
        for i in range(len(control_points) - 1):
            point1 = (control_points[i][1], control_points[i][0])  # 纬度, 经度
            point2 = (control_points[i+1][1], control_points[i+1][0])  # 纬度, 经度
            
            # 计算段距离（公里）
            segment_distance = geodesic(point1, point2).kilometers
            
            # 计算这段需要的点数
            # 1节 ≈ 1.852 km/h，time_step_minutes分钟内的距离
            distance_per_step = vessel_speed_knots * 1.852 * (time_step_minutes / 60)
            segment_points = max(2, int(segment_distance / distance_per_step))
            segment_counts.append(segment_points)
            
            # 线性插值
            lons = np.linspace(control_points[i][0], control_points[i+1][0], segment_points)
            lats = np.linspace(control_points[i][1], control_points[i+1][1], segment_points)
            
            # 添加该段的点（除了最后一段，避免重复添加终点）
            if i < len(control_points) - 2:
                segment_points = np.column_stack([lons, lats])
                smooth_points.extend(segment_points[:-1])
            else:
                segment_points = np.column_stack([lons, lats])
                smooth_points.extend(segment_points)
        
        smooth_points = np.array(smooth_points)
    else:
        raise ValueError("不支持的插值方法。请选择 'bezier' 或 'linear'")
    
    # 计算每个点之间的距离
    distances = []
    for i in range(len(smooth_points) - 1):
        point1 = (smooth_points[i][1], smooth_points[i][0])  # 纬度, 经度
        point2 = (smooth_points[i+1][1], smooth_points[i+1][0])  # 纬度, 经度
        distances.append(geodesic(point1, point2).kilometers)
    
    # 计算各点的时间戳和速度
    times = [start_time]
    speeds = []
    total_distance = 0
    
    # 为每个点设置基于距离的时间和变化的速度
    base_speed = vessel_speed_knots
    current_speed = base_speed
    
    for i, distance in enumerate(distances):
        # 引入速度变化
        if include_noise:
            speed_factor = 1.0 + np.random.uniform(-speed_variation, speed_variation)
            current_speed = base_speed * speed_factor
        else:
            current_speed = base_speed
            
        speeds.append(current_speed)
        
        # 计算该距离所需时间（小时）
        time_hours = distance / (current_speed * 1.852)
        # 转换为分钟并创建时间增量
        time_minutes = time_hours * 60
        time_delta = timedelta(minutes=time_minutes)
        
        # 添加到前一个时间点
        next_time = times[-1] + time_delta
        times.append(next_time)
        
        # 累计总距离
        total_distance += distance
    
    # 为起点添加速度（与第一段相同）
    speeds.insert(0, speeds[0] if speeds else base_speed)
    
    # 添加轨迹噪声（模拟GPS误差等）
    if include_noise:
        noise_lon = np.random.normal(0, noise_level, len(smooth_points))
        noise_lat = np.random.normal(0, noise_level, len(smooth_points))
        smooth_points[:, 0] += noise_lon
        smooth_points[:, 1] += noise_lat
    
    # 创建轨迹DataFrame
    trajectory_data = {
        'timestamp': times,
        'longitude': smooth_points[:, 0],
        'latitude': smooth_points[:, 1],
        'speed_knots': speeds,
        'cumulative_distance_km': [0] + [sum(distances[:i+1]) for i in range(len(distances))]
    }
    
    trajectory_df = pd.DataFrame(trajectory_data)
    
    # 添加航向信息（基于相邻点之间的方位角）
    headings = [0]  # 初始航向（将在下面被更新）
    
    for i in range(len(smooth_points) - 1):
        # 计算航向角（假设经纬度坐标系）
        y1, x1 = smooth_points[i][1], smooth_points[i][0]  # 纬度, 经度
        y2, x2 = smooth_points[i+1][1], smooth_points[i+1][0]  # 纬度, 经度
        
        dx = x2 - x1
        dy = y2 - y1
        
        # 计算方位角（0°为北，顺时针增加）
        heading = (90 - math.degrees(math.atan2(dy, dx))) % 360
        headings.append(heading)
    
    # 更新第一个点的航向（与第二个点相同）
    headings[0] = headings[1]
    
    # 添加航向到DataFrame
    trajectory_df['heading'] = headings
    
    return trajectory_df


def plot_vessel_trajectory(trajectory_df, control_points=None, map_style='terrain', figsize=(12, 10), 
                          plot_time_markers=True, time_marker_interval=6):
    """
    可视化船舶轨迹
    
    :param trajectory_df: 由generate_vessel_trajectory函数生成的轨迹DataFrame
    :param control_points: 可选，原始控制点列表
    :param map_style: 地图样式，可选 'terrain'、'satellite' 或 'plain'
    :param figsize: 图形大小
    :param plot_time_markers: 是否在轨迹上标记时间点
    :param time_marker_interval: 时间标记间隔（小时）
    :return: matplotlib figure和axes对象
    """
    try:
        import matplotlib.pyplot as plt
        import numpy as np
        import contextily as ctx
        from matplotlib.colors import LinearSegmentedColormap
    except ImportError:
        print("请安装所需包: pip install matplotlib contextily")
        return None, None
    
    fig, ax = plt.subplots(figsize=figsize)
    
    # 提取轨迹数据
    lons = trajectory_df['longitude'].values
    lats = trajectory_df['latitude'].values
    speeds = trajectory_df['speed_knots'].values
    
    # 确保时间戳是Python datetime对象
    if isinstance(trajectory_df['timestamp'].iloc[0], (np.datetime64, pd.Timestamp)):
        times = trajectory_df['timestamp'].dt.to_pydatetime()
    else:
        times = trajectory_df['timestamp'].values
    
    # 创建自定义颜色映射，基于速度
    colors = ['blue', 'green', 'yellow', 'red']
    custom_cmap = LinearSegmentedColormap.from_list('custom_cmap', colors)
    
    # 绘制轨迹
    points = np.column_stack([lons, lats])
    speed_norm = plt.Normalize(min(speeds), max(speeds))
    
    for i in range(len(points) - 1):
        ax.plot([points[i, 0], points[i+1, 0]], [points[i, 1], points[i+1, 1]], 
                color=custom_cmap(speed_norm(speeds[i])), linewidth=2, alpha=0.8)
    
    # 标记起点和终点
    ax.scatter(lons[0], lats[0], c='green', s=100, edgecolor='white', linewidth=2, label='起点')
    ax.scatter(lons[-1], lats[-1], c='red', s=100, edgecolor='white', linewidth=2, label='终点')
    
    # 绘制控制点
    if control_points is not None:
        control_points = np.array(control_points)
        ax.scatter(control_points[:, 0], control_points[:, 1], c='purple', s=80, 
                  edgecolor='white', linewidth=1.5, label='控制点')
    
    # 添加时间标记
    if plot_time_markers:
        # 计算总时间差（小时）
        try:
            # 处理Python datetime对象
            start_time = times[0]
            end_time = times[-1]
            if isinstance(start_time, datetime):
                time_diff = (end_time - start_time).total_seconds() / 3600
            # 处理numpy或pandas时间对象
            elif isinstance(start_time, (np.datetime64, pd.Timestamp)):
                time_diff = (end_time - start_time) / np.timedelta64(1, 'h')
            else:
                # 如果是其他类型，尝试转换
                time_diff = (pd.to_datetime(end_time) - pd.to_datetime(start_time)).total_seconds() / 3600
        except:
            # 如果无法计算时间差，设置默认值
            time_diff = 24
            print("警告：无法计算时间差，使用默认值")
        
        if time_diff > 0:
            # 根据总时间调整标记间隔
            if time_diff < 1:  # 不到1小时
                time_marker_interval = 0.1  # 每6分钟
            elif time_diff < 5:  # 不到5小时
                time_marker_interval = 0.5  # 每30分钟
            
            time_indices = []
            current_hour = 0
            
            for i, time in enumerate(times):
                # 计算经过的时间（小时）
                if isinstance(time, datetime) and isinstance(times[0], datetime):
                    hours_elapsed = (time - times[0]).total_seconds() / 3600
                elif isinstance(time, (np.datetime64, pd.Timestamp)):
                    hours_elapsed = (time - times[0]) / np.timedelta64(1, 'h')
                else:
                    try:
                        hours_elapsed = (pd.to_datetime(time) - pd.to_datetime(times[0])).total_seconds() / 3600
                    except:
                        print(f"警告：时间格式不支持: {type(time)}")
                        continue
                
                if hours_elapsed >= current_hour:
                    time_indices.append(i)
                    current_hour += time_marker_interval
            
            # 绘制时间标记
            for idx in time_indices:
                if idx < len(lons):  # 确保索引有效
                    ax.scatter(lons[idx], lats[idx], c='white', s=50, edgecolor='black', zorder=5)
                    
                    # 格式化时间文本
                    if isinstance(times[idx], datetime):
                        time_text = times[idx].strftime('%H:%M')
                    elif isinstance(times[idx], (np.datetime64, pd.Timestamp)):
                        time_text = pd.to_datetime(times[idx]).strftime('%H:%M')
                    else:
                        time_text = str(times[idx])
                    
                    ax.annotate(time_text, (lons[idx], lats[idx]), xytext=(5, 5), 
                               textcoords='offset points', fontsize=8, 
                               bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="black", alpha=0.7))
    
    # 添加背景地图
    try:
        # 获取边界扩展一点，以便更好地显示
        buffer = 0.02  # 边界缓冲区
        min_lon, max_lon = min(lons) - buffer, max(lons) + buffer
        min_lat, max_lat = min(lats) - buffer, max(lats) + buffer
        
        # 选择地图样式
        if map_style == 'terrain':
            ctx.add_basemap(ax, source=ctx.providers.OpenTopoMap, crs="EPSG:4326")
        elif map_style == 'satellite':
            ctx.add_basemap(ax, source=ctx.providers.Esri.WorldImagery, crs="EPSG:4326")
        else:  # plain
            ctx.add_basemap(ax, source=ctx.providers.CartoDB.Positron, crs="EPSG:4326")
        
        # 设置地图范围
        ax.set_xlim(min_lon, max_lon)
        ax.set_ylim(min_lat, max_lat)
    except Exception as e:
        print(f"添加背景地图失败: {e}")
        print("继续使用普通图形...")
    
    # 添加色标，表示速度
    sm = plt.cm.ScalarMappable(cmap=custom_cmap, norm=speed_norm)
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, orientation='vertical', pad=0.01)
    cbar.set_label('速度（节）')
    
    # 设置图形标题和标签
    plt.title('船舶轨迹', fontsize=16, pad=20)
    plt.xlabel('经度', fontsize=12)
    plt.ylabel('纬度', fontsize=12)
    
    # 添加图例
    plt.legend(loc='upper right')
    
    # 添加总航行信息
    try:
        total_distance = trajectory_df['cumulative_distance_km'].iloc[-1]
        
        # 计算时间差
        if isinstance(times[0], datetime) and isinstance(times[-1], datetime):
            duration = (times[-1] - times[0]).total_seconds() / 3600
        elif isinstance(times[0], (np.datetime64, pd.Timestamp)):
            duration = (times[-1] - times[0]) / np.timedelta64(1, 'h')
        else:
            duration = (pd.to_datetime(times[-1]) - pd.to_datetime(times[0])).total_seconds() / 3600
        
        avg_speed = total_distance / duration if duration > 0 else 0
        
        # 格式化时间
        if isinstance(times[0], datetime):
            start_str = times[0].strftime('%Y-%m-%d %H:%M')
            end_str = times[-1].strftime('%Y-%m-%d %H:%M')
        elif isinstance(times[0], (np.datetime64, pd.Timestamp)):
            start_str = pd.to_datetime(times[0]).strftime('%Y-%m-%d %H:%M')
            end_str = pd.to_datetime(times[-1]).strftime('%Y-%m-%d %H:%M')
        else:
            start_str = str(times[0])
            end_str = str(times[-1])
        
        info_text = (
            f"总航程: {total_distance:.2f} km\n"
            f"起始时间: {start_str}\n"
            f"结束时间: {end_str}\n"
            f"航行时间: {duration:.2f} 小时\n"
            f"平均速度: {avg_speed:.2f} km/h"
        )
        
        plt.figtext(0.01, 0.01, info_text, fontsize=10,
                   bbox=dict(boxstyle="round,pad=0.5", fc="white", ec="black", alpha=0.8))
    except Exception as e:
        print(f"添加航行信息失败: {e}")
    
    # 调整布局
    plt.tight_layout()
    
    return fig, ax


def export_trajectory_to_geojson(trajectory_df, filename='vessel_trajectory.geojson'):
    """
    将轨迹导出为GeoJSON格式
    
    :param trajectory_df: 轨迹DataFrame
    :param filename: 输出文件名
    :return: GeoJSON字符串
    """
    try:
        import geopandas as gpd
        from shapely.geometry import LineString, Point
        import json
    except ImportError:
        print("请安装所需包: pip install geopandas shapely")
        return None
    
    # 确保时间戳可以正确JSON序列化
    def format_timestamp(ts):
        if isinstance(ts, datetime):
            return ts.isoformat()
        elif isinstance(ts, (np.datetime64, pd.Timestamp)):
            return pd.to_datetime(ts).isoformat()
        else:
            return str(ts)
    
    # 创建点特征集合
    points = []
    for _, row in trajectory_df.iterrows():
        point = Point(row['longitude'], row['latitude'])
        points.append({
            'type': 'Feature',
            'geometry': {
                'type': 'Point',
                'coordinates': [row['longitude'], row['latitude']]
            },
            'properties': {
                'timestamp': format_timestamp(row['timestamp']),
                'speed_knots': float(row['speed_knots']),
                'heading': float(row['heading']),
                'distance_km': float(row['cumulative_distance_km'])
            }
        })
    
    # 创建线特征（整个轨迹）
    coordinates = [(row['longitude'], row['latitude']) for _, row in trajectory_df.iterrows()]
    line = {
        'type': 'Feature',
        'geometry': {
            'type': 'LineString',
            'coordinates': coordinates
        },
        'properties': {
            'start_time': format_timestamp(trajectory_df['timestamp'].iloc[0]),
            'end_time': format_timestamp(trajectory_df['timestamp'].iloc[-1]),
            'total_distance_km': float(trajectory_df['cumulative_distance_km'].iloc[-1]),
            'avg_speed_knots': float(trajectory_df['speed_knots'].mean())
        }
    }
    
    # 组合为GeoJSON集合
    geojson = {
        'type': 'FeatureCollection',
        'features': [line] + points
    }
    
    # 导出到文件
    with open(filename, 'w') as f:
        json.dump(geojson, f, indent=2)
    
    print(f"轨迹已导出到: {filename}")
    return geojson


# 使用示例
if __name__ == "__main__":
    # 示例控制点（经度，纬度）
    control_points = [
        (122.382, 25.765),     # 上海附近
        (123.651, 26.067),     # 中间点1
        (125.178, 26.863),     # 中间点2
        (126.958, 29.191),     # 拐点
        (124.288, 29.879)      # 终点
    ]
    
    # 生成轨迹
    trajectory = generate_vessel_trajectory(
        control_points=control_points,
        vessel_speed_knots=12,
        time_step_minutes=5,
        interpolate_method='bezier',
        start_time="2023-06-01 08:00:00",
        speed_variation=0.15,
        include_noise=True,
        noise_level=0.0005
    )
    
    # 查看轨迹数据
    print(trajectory.head())
    
    # # 可视化轨迹
    # fig, ax = plot_vessel_trajectory(
    #     trajectory,
    #     control_points=control_points,
    #     map_style='terrain',
    #     figsize=(14, 10),
    #     plot_time_markers=True
    # )
    
    # # 显示图形
    # plt.show()
    
    # 导出为GeoJSON（可选）
    export_trajectory_to_geojson(trajectory, '../results/example_trajectory.geojson')
