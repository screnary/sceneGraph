import folium
from folium.plugins import HeatMap, MeasureControl, Fullscreen, TimestampedGeoJson
import os
import webbrowser
import copy
import pandas as pd
import numpy as np
from datetime import datetime
import graph_utils as GU
import pdb

# 时间点动画显示的修改版本
def visualize_scene_graph(graph, filename="scene_graph_map.html", center_coordinate=None, 
                          filter_min_weight=None, draw_bounds=True, trajectory_df=None,
                          animate=False, time_interval=1000, ship_node_id="ship_001"):
    """
    创建场景图的地理可视化
    
    :param graph: SceneGraph对象
    :param filename: 输出的HTML文件名
    :param center_coordinate: 可选，地图中心坐标，格式为"经度,纬度"
    :param filter_min_weight: 可选，过滤低于此权重的边
    :param draw_bounds: 可选，绘制环境节点影响范围bbox
    :param trajectory_df: 可选，轨迹DataFrame，包含timestamp、longitude、latitude等列
    :param animate: 是否制作轨迹动画
    :param time_interval: 动画中每帧之间的间隔（毫秒）
    :param ship_node_id: 船舶节点的ID
    :return: folium.Map对象, graph_series, timestamps
    """
    graph_series = []
    timestamps = []

    # 确保输出目录存在
    output_dir = os.path.dirname(filename)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # 分析是否使用轨迹模式
    trajectory_mode = trajectory_df is not None and not trajectory_df.empty

    # 在轨迹模式下，预处理轨迹数据
    if trajectory_mode:
        # 确保时间戳是datetime类型
        if 'timestamp' in trajectory_df.columns and not pd.api.types.is_datetime64_any_dtype(trajectory_df['timestamp']):
            try:
                trajectory_df['timestamp'] = pd.to_datetime(trajectory_df['timestamp'])
            except:
                print("警告: 无法将时间戳转换为datetime类型")
        
        # 确保经纬度列存在
        if 'longitude' not in trajectory_df.columns or 'latitude' not in trajectory_df.columns:
            print("警告: 轨迹数据缺少经度或纬度列")
            trajectory_mode = False
        else:
            # 排序轨迹数据
            if 'timestamp' in trajectory_df.columns:
                trajectory_df = trajectory_df.sort_values('timestamp')
    
    # compute map center
    if not center_coordinate:
        # 收集所有节点的经纬度坐标
        coordinates = []
        
        # 添加基础场景图中的节点坐标
        for node_id, node in graph.nodes.items():
            location = node.attributes.get("Location")
            if location:
                try:
                    lon, lat = map(float, location.split(","))
                    coordinates.append((lat, lon))  # Folium使用(lat, lon)格式
                except:
                    continue
        
        # 添加轨迹中的坐标
        if trajectory_mode:
            for _, row in trajectory_df.iterrows():
                coordinates.append((row['latitude'], row['longitude']))
        
        # 如果没有坐标，使用默认中心点
        if not coordinates:
            center = [0, 0]
            zoom_start = 2
        else:
            # 计算平均位置作为地图中心
            lat_avg = sum(lat for lat, _ in coordinates) / len(coordinates)
            lon_avg = sum(lon for _, lon in coordinates) / len(coordinates)
            center = [lat_avg, lon_avg]
            zoom_start = 5
    else:
        lon, lat = map(float, center_coordinate.split(","))
        center = [lat, lon]
        zoom_start = 5
    
    # 创建地图，使用 ESRI 海洋底图作为默认图层
    m = folium.Map(
        location=center, 
        zoom_start=zoom_start,
        tiles='OpenStreetMap',
        name='OpenStreetMap'
    )
    
    # m = folium.Map(
    #     location=center, 
    #     zoom_start=zoom_start,
    #     tiles='https://server.arcgisonline.com/ArcGIS/rest/services/Ocean/World_Ocean_Base/MapServer/tile/{z}/{y}/{x}',
    #     attr='Esri, GEBCO, NOAA, National Geographic, DeLorme',
    #     name='ESRI Ocean'
    # )

    # # 添加其他地图图层选项
    # folium.TileLayer(
    #     tiles='OpenStreetMap',
    #     name='OpenStreetMap'
    # ).add_to(m)

    # ESRI 海洋参考层 (地名标签)
    # esri_ocean_ref = folium.TileLayer(
    #     tiles='https://server.arcgisonline.com/ArcGIS/rest/services/Ocean/World_Ocean_Reference/MapServer/tile/{z}/{y}/{x}',
    #     attr='Esri, GEBCO, NOAA, National Geographic',
    #     name='ESRI 海洋标签',
    #     overlay=True
    # )
    # esri_ocean_ref.add_to(m)

    # 添加 OpenSeaMap 航海图层
    try:
        folium.TileLayer(
            tiles='https://tiles.openseamap.org/seamark/{z}/{x}/{y}.png',
            attr='OpenSeaMap',
            name='OpenSeaMap Navigation',
            overlay=True
        ).add_to(m)
    except Exception as e:
        print(f"无法加载OpenSeaMap图层: {e}")

    # CartoDB Voyager (航海风格地图)
    try:
        carto_voyager = folium.TileLayer(
            tiles='https://cartodb-basemaps-{s}.global.ssl.fastly.net/rastertiles/voyager/{z}/{x}/{y}{r}.png',
            attr='CartoDB',
            name='CartoDB Voyager',
            overlay=False
        )
        carto_voyager.add_to(m)
    except Exception as e:
        print(f"无法加载CartoDB图层: {e}")

    # 尝试添加 NOAA 电子航海图 (如果可用)
    try:
        noaa_enc = folium.TileLayer(
            tiles='https://tileservice.charts.noaa.gov/tiles/50000_1/{z}/{x}/{y}.png',
            attr='NOAA Office of Coast Survey',
            name='NOAA 电子航海图',
            overlay=False
        )
        noaa_enc.add_to(m)
    except Exception as e:
        print(f"无法加载NOAA图层: {e}")
    
    # 创建图层组
    equipment_layer = folium.FeatureGroup(name="装备")
    environment_layers = {}  # 按环境类型分组
    
    # 添加静态环境节点
    env_type_colors = {
        "锋面": "red",
        "风暴增水": "orange",
        "中尺度涡": "green"
    }
    
    for node_id, node in graph.nodes.items():
        if node.node_type == "Environment":
            env_type = node.attributes.get("Name", "未知")
            
            # 为每种环境类型创建图层
            if env_type not in environment_layers:
                environment_layers[env_type] = folium.FeatureGroup(name=f"环境 - {env_type}")
            
            location = node.attributes.get("Location")
            if location:
                try:
                    lon, lat = map(float, location.split(","))
                    
                    # 创建弹出框内容
                    popup_html = f"""
                    <div>
                        <h4>{env_type} - {node_id}</h4>
                    """
                    
                    # 添加环境参数值
                    values = node.attributes.get("Value", {})
                    for key, value in values.items():
                        popup_html += f"<p><b>{key}:</b> {value}</p>"
                    
                    popup_html += "</div>"
                    
                    # 获取此环境类型的颜色
                    color = env_type_colors.get(env_type, "gray")
                    
                    # 添加环境标记
                    folium.CircleMarker(
                        [lat, lon],
                        radius=5,
                        popup=folium.Popup(popup_html, max_width=300),
                        tooltip=f"{env_type} ({values.get(env_type, 'N/A')})",
                        color=color,
                        fill=True,
                        fill_color=color,
                        fill_opacity=0.7
                    ).add_to(environment_layers[env_type])
                    
                    # 如果有边界信息，添加矩形
                    bounds = node.attributes.get("bounds")
                    if bounds and draw_bounds:
                        try:
                            folium.Rectangle(
                                bounds=[[bounds.min_lat, bounds.min_lon], 
                                       [bounds.max_lat, bounds.max_lon]],
                                color=color,
                                weight=1,
                                fill=True,
                                fill_color=color,
                                fill_opacity=0.05,
                                tooltip=f"{env_type} - {node_id}"
                            ).add_to(environment_layers[env_type])
                        except Exception as e:
                            print(f"无法绘制边界 {node_id}: {e}")
                
                except Exception as e:
                    print(f"无法处理环境节点 {node_id} 的位置: {e}")
    
    # 非轨迹模式或不需要动画时，显示静态装备节点和边
    if not trajectory_mode or not animate:
        edge_layer = folium.FeatureGroup(name="关系")
        
        # 添加设备节点
        for node_id, node in graph.nodes.items():
            if node.node_type == "Equipment":
                location = node.attributes.get("Location")
                if location:
                    try:
                        lon, lat = map(float, location.split(","))
                        
                        # 创建弹出框内容
                        popup_html = f"""
                        <div style="width:250px">
                            <h4>{node.attributes.get('Name', node_id)}</h4>
                            <p><b>ID:</b> {node_id}</p>
                            <p><b>功能:</b> {node.attributes.get('Function', 'N/A')}</p>
                            <p><b>状态:</b> {node.attributes.get('Status', 'N/A')}</p>
                            <hr>
                            <p><b>支持的环境参数:</b></p>
                        """
                        
                        supported_env = node.attributes.get("Supported_Environment", {})
                        for env_type, range_values in supported_env.items():
                            popup_html += f"<p>{env_type}: {range_values[0]} - {range_values[1]}</p>"
                        
                        popup_html += "</div>"
                        
                        # 添加设备标记
                        folium.Marker(
                            [lat, lon],
                            popup=folium.Popup(popup_html, max_width=300),
                            tooltip=node.attributes.get('Name', node_id),
                            icon=folium.Icon(color='blue', icon='ship', prefix='fa')
                        ).add_to(equipment_layer)
                        
                    except Exception as e:
                        print(f"无法处理设备节点 {node_id} 的位置: {e}")
        
        # 添加静态边（关系）
        for edge in graph.edges:
            # 如果设置了权重过滤，跳过低权重的边
            if filter_min_weight is not None and edge.weight < filter_min_weight:
                continue
            
            source_node = edge.source_node
            target_node = edge.target_node
            
            source_location = source_node.attributes.get("Location")
            target_location = target_node.attributes.get("Location")
            
            if source_location and target_location:
                try:
                    source_lon, source_lat = map(float, source_location.split(","))
                    target_lon, target_lat = map(float, target_location.split(","))
                    
                    # 根据边类型和权重确定颜色
                    edge_color = "gray"  # 默认颜色
                    
                    if edge.edge_type == "NotCompatible":
                        # 不兼容的边用红色
                        intensity = min(1.0, edge.weight)  # 确保在0-1范围内
                        edge_color = f'rgb({int(255)}, {int(165 * (1-intensity))}, 0)'
                    elif edge.edge_type == "Compatible":
                        # 兼容的边用绿色
                        edge_color = "green"
                    
                    # 创建边的弹出框内容
                    popup_html = f"""
                    <div>
                        <h4>关系: {edge.edge_type}</h4>
                        <p><b>源节点:</b> {source_node.node_id} ({source_node.attributes.get('Name', 'N/A')})</p>
                        <p><b>目标节点:</b> {target_node.node_id} ({target_node.attributes.get('Name', 'N/A')})</p>
                        <p><b>权重:</b> {edge.weight:.3f}</p>
                    """
                    
                    # 添加原因（如果有）
                    if hasattr(edge, 'attributes') and "Reason" in edge.attributes:
                        popup_html += f"<p><b>原因:</b> {edge.attributes['Reason']}</p>"
                    
                    popup_html += "</div>"
                    
                    # 根据权重调整线宽
                    line_weight = 1 + min(5, 9 * edge.weight)  # 权重0对应宽度1，权重1对应宽度6
                    
                    # 添加边
                    folium.PolyLine(
                        locations=[[source_lat, source_lon], [target_lat, target_lon]],
                        color=edge_color,
                        weight=line_weight,
                        opacity=0.7,
                        popup=folium.Popup(popup_html, max_width=300),
                        tooltip=f"{edge.edge_type} (权重: {edge.weight:.2f})"
                    ).add_to(edge_layer)
                
                except Exception as e:
                    print(f"无法绘制边 {source_node.node_id} -> {target_node.node_id}: {e}")
    
        # 添加边缘图层到地图
        edge_layer.add_to(m)
    
    # 轨迹模式下的处理
    if trajectory_mode:
        # 创建轨迹图层
        trajectory_layer = folium.FeatureGroup(name="船舶轨迹")
        
        # 绘制完整轨迹线
        trajectory_points = [[row['latitude'], row['longitude']] for _, row in trajectory_df.iterrows()]
        folium.PolyLine(
            trajectory_points,
            color="blue",
            weight=3,
            opacity=0.4,
            tooltip="船舶轨迹"
        ).add_to(trajectory_layer)
        
        # 标记起点和终点
        if len(trajectory_points) > 0:
            # 起点 (绿色)
            folium.Marker(
                trajectory_points[0],
                tooltip="起点",
                icon=folium.Icon(color='green', icon='play', prefix='fa')
            ).add_to(trajectory_layer)
            
            # 终点 (红色)
            folium.Marker(
                trajectory_points[-1],
                tooltip="终点",
                icon=folium.Icon(color='red', icon='stop', prefix='fa')
            ).add_to(trajectory_layer)
        
        # 添加轨迹图层到地图
        trajectory_layer.add_to(m)

        # 动画模式 - 完全重写这部分代码
        if animate:
            # 设置每小时采样
            sampling_interval = pd.Timedelta(hours=1)  # 每小时采样一次
            
            # 创建复制的原始图作为基础
            base_graph = GU.copy_graph(graph)
            
            # 按时间点创建图层 - 关键改变
            time_layers = []
            
            # 如果timestamp列存在，按小时采样轨迹点
            if 'timestamp' in trajectory_df.columns and pd.api.types.is_datetime64_any_dtype(trajectory_df['timestamp']):
                # 确保时间戳排序
                trajectory_df = trajectory_df.sort_values('timestamp')
                
                # 获取轨迹的时间范围
                start_time = trajectory_df['timestamp'].min()
                end_time = trajectory_df['timestamp'].max()
                
                # 创建每小时的采样时间点
                current_hour = pd.Timestamp(start_time.year, start_time.month, start_time.day, 
                                          start_time.hour, 0, 0)
                sampled_times = []
                
                # 生成整点时间序列
                while current_hour <= end_time:
                    sampled_times.append(current_hour)
                    current_hour += sampling_interval
                
                # 确保有足够的采样点
                if len(sampled_times) < 2:
                    sampled_times = [start_time, end_time]
                
                # 对每个采样时间点，找到最接近的轨迹点
                for i, sample_time in enumerate(sampled_times):
                    # 找到最接近此时间的轨迹点
                    trajectory_df['time_diff'] = abs(trajectory_df['timestamp'] - sample_time)
                    closest_idx = trajectory_df['time_diff'].idxmin()
                    row = trajectory_df.loc[closest_idx]
                    
                    # 格式化时间戳为字符串
                    time_str = sample_time.strftime('%Y-%m-%d %H:%M:%S')
                    time_display = sample_time.strftime('%m-%d %H:%M')  # 更简短的显示格式
                    
                    # 关键改变: 为每个时间点创建一个独立的图层组
                    time_layer = folium.FeatureGroup(name=f"时间点 {time_display}")
                    
                    # 更新图中船舶节点的位置
                    current_graph = GU.copy_graph(base_graph)
                    ship_node = current_graph.get_node(ship_node_id)
                    
                    if ship_node:
                        # 更新船舶位置
                        ship_node.update_attribute({
                            'Location': f"{row['longitude']:.6f}, {row['latitude']:.6f}"
                        })
                        
                        # 如果有速度和航向信息，也更新
                        if 'speed_knots' in row:
                            ship_node.update_attribute({
                                ('Value', 'Speed'): f"{row['speed_knots']:.2f} knots"
                            })
                        
                        if 'heading' in row:
                            ship_node.update_attribute({
                                ('Value', 'Heading'): f"{row['heading']:.1f}°"
                            })
                        
                        # 重新计算边的权重
                        current_graph.calculate_edge_weights()
                        
                        # 添加船舶位置标记
                        popup_html = f"""
                        <div style="width:250px">
                            <h4>船舶位置</h4>
                            <p><b>时间:</b> {time_str}</p>
                            <p><b>位置:</b> {row['latitude']:.6f}, {row['longitude']:.6f}</p>
                            {f'<p><b>速度:</b> {row["speed_knots"]:.2f} knots</p>' if 'speed_knots' in row else ''}
                            {f'<p><b>航向:</b> {row["heading"]:.1f}°</p>' if 'heading' in row else ''}
                        </div>
                        """
                        
                        folium.Marker(
                            [row['latitude'], row['longitude']],
                            popup=folium.Popup(popup_html, max_width=300),
                            tooltip=f"船舶位置 ({time_display})",
                            icon=folium.Icon(icon='ship', prefix='fa', color='blue')
                        ).add_to(time_layer)
                        
                        # 添加船舶相关的边
                        for edge in current_graph.edges:
                            # 过滤低权重边
                            if filter_min_weight is not None and edge.weight < filter_min_weight:
                                continue
                                
                            source_node = edge.source_node
                            target_node = edge.target_node
                            
                            # 只显示与船舶相关的边
                            if source_node.node_id != ship_node_id and target_node.node_id != ship_node_id:
                                continue
                                
                            source_location = source_node.attributes.get("Location")
                            target_location = target_node.attributes.get("Location")
                            
                            if source_location and target_location:
                                try:
                                    source_lon, source_lat = map(float, source_location.split(","))
                                    target_lon, target_lat = map(float, target_location.split(","))
                                    
                                    # 确定边的颜色
                                    edge_color = "gray"  # 默认颜色
                                    if edge.edge_type == "NotCompatible":
                                        intensity = min(1.0, edge.weight)  # 确保在0-1范围内
                                        edge_color = f'rgb({int(255)}, {int(165 * (1-intensity))}, 0)'
                                    elif edge.edge_type == "Compatible":
                                        edge_color = "green"
                                    
                                    # 根据权重调整线宽
                                    line_weight = 2 + min(5, 9 * edge.weight)
                                    
                                    # 添加边到时间图层
                                    folium.PolyLine(
                                        locations=[[source_lat, source_lon], [target_lat, target_lon]],
                                        color=edge_color,
                                        weight=line_weight,
                                        opacity=0.8,
                                        popup=f"<h4>关系: {edge.edge_type}</h4><p>权重: {edge.weight:.3f}</p>",
                                        tooltip=f"{edge.edge_type} (权重: {edge.weight:.2f})"
                                    ).add_to(time_layer)
                                except Exception as e:
                                    print(f"处理动态边时出错: {e}")
                    
                    # 将创建的时间图层添加到时间图层列表
                    time_layers.append({
                        'layer': time_layer,
                        'time': time_str,
                        'display': time_display
                    })
                    
                    # 将图层添加到地图 - 所有时间图层都添加
                    time_layer.add_to(m)
                    graph_series.append(current_graph)
                    timestamps.append(time_str)
            else:
                # 如果没有timestamp列，采用简化处理...
                print("轨迹数据没有有效的时间戳列，将使用等间隔采样")
                # 简略代码...
            
            # 添加自定义时间点选择控制器
            custom_control_html = """
            <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.3.1/css/bootstrap.min.css">
            <style>
                #time-control {
                    position: absolute;
                    bottom: 20px;
                    left: 50%;
                    transform: translateX(-50%);
                    z-index: 1000;
                    background: white;
                    padding: 10px;
                    border-radius: 5px;
                    box-shadow: 0 2px 5px rgba(0,0,0,0.3);
                    max-width: 600px;
                    width: 90%;
                }
                .time-btn {
                    margin: 2px;
                    font-size: 12px;
                    padding: 2px 6px;
                }
                .time-btn.active {
                    background-color: #007bff;
                    color: white;
                }
                .control-row {
                    display: flex;
                    justify-content: center;
                    margin-bottom: 8px;
                }
            </style>
            
            <div id="time-control">
                <div class="control-row">
                    <button id="prev-btn" class="btn btn-sm btn-outline-secondary mr-2">上一步</button>
                    <button id="play-btn" class="btn btn-sm btn-outline-primary">播放</button>
                    <button id="next-btn" class="btn btn-sm btn-outline-secondary ml-2">下一步</button>
                </div>
                <div id="time-buttons" class="d-flex flex-wrap justify-content-center">
            """
            
            # 为每个时间点添加按钮
            for i, time_data in enumerate(time_layers):
                active_class = "active" if i == 0 else ""
                custom_control_html += f"""
                    <button class="btn btn-sm btn-outline-info time-btn {active_class}" 
                            data-index="{i}" data-time="{time_data['time']}">
                        {time_data['display']}
                    </button>
                """
            
            custom_control_html += """
                </div>
            </div>
            
            <script>
                // 在地图加载完成后执行
                window.addEventListener('load', function() {
                    console.log('地图加载完成，初始化时间控制器');
                    
                    // 获取所有时间图层的复选框，通过它们控制图层显示
                    var timeLayerCheckboxes = Array.from(document.querySelectorAll('.leaflet-control-layers-overlays input[type="checkbox"]'))
                        .filter(function(checkbox) {
                            return checkbox.nextSibling && checkbox.nextSibling.textContent.includes('时间点');
                        });
                    
                    console.log('找到 ' + timeLayerCheckboxes.length + ' 个时间图层复选框');
                    
                    // 初始状态：只显示第一个时间点，隐藏其他
                    function showTimePoint(index) {
                        timeLayerCheckboxes.forEach(function(checkbox, i) {
                            if (i === index) {
                                if (!checkbox.checked) checkbox.click();
                            } else {
                                if (checkbox.checked) checkbox.click();
                            }
                        });
                        
                        // 更新按钮状态
                        document.querySelectorAll('.time-btn').forEach(function(btn, i) {
                            if (i === index) {
                                btn.classList.add('active');
                            } else {
                                btn.classList.remove('active');
                            }
                        });
                    }
                    
                    // 初始化显示第一个时间点
                    showTimePoint(0);
                    
                    // 当前显示的时间点索引
                    var currentIndex = 0;
                    var isPlaying = false;
                    var playInterval;
                    
                    // 为每个时间按钮添加点击事件
                    document.querySelectorAll('.time-btn').forEach(function(btn) {
                        btn.addEventListener('click', function() {
                            // 停止自动播放
                            stopPlaying();
                            
                            // 获取并显示点击的时间点
                            var index = parseInt(this.getAttribute('data-index'));
                            currentIndex = index;
                            showTimePoint(index);
                        });
                    });
                    
                    // 播放/暂停按钮
                    var playBtn = document.getElementById('play-btn');
                    playBtn.addEventListener('click', function() {
                        if (isPlaying) {
                            stopPlaying();
                        } else {
                            startPlaying();
                        }
                    });
                    
                    function startPlaying() {
                        isPlaying = true;
                        playBtn.textContent = '暂停';
                        playBtn.classList.remove('btn-outline-primary');
                        playBtn.classList.add('btn-primary');
                        
                        // 每2秒切换到下一个时间点
                        playInterval = setInterval(function() {
                            currentIndex = (currentIndex + 1) % timeLayerCheckboxes.length;
                            showTimePoint(currentIndex);
                        }, 2000);
                    }
                    
                    function stopPlaying() {
                        if (isPlaying) {
                            clearInterval(playInterval);
                            isPlaying = false;
                            playBtn.textContent = '播放';
                            playBtn.classList.remove('btn-primary');
                            playBtn.classList.add('btn-outline-primary');
                        }
                    }
                    
                    // 上一步/下一步按钮
                    document.getElementById('prev-btn').addEventListener('click', function() {
                        stopPlaying();
                        currentIndex = (currentIndex - 1 + timeLayerCheckboxes.length) % timeLayerCheckboxes.length;
                        showTimePoint(currentIndex);
                    });
                    
                    document.getElementById('next-btn').addEventListener('click', function() {
                        stopPlaying();
                        currentIndex = (currentIndex + 1) % timeLayerCheckboxes.length;
                        showTimePoint(currentIndex);
                    });
                    
                    // 隐藏图层控制器中的时间图层标签，避免用户直接点击
                    var layerLabels = document.querySelectorAll('.leaflet-control-layers-overlays label');
                    layerLabels.forEach(function(label) {
                        if (label.textContent.includes('时间点')) {
                            label.style.display = 'none';
                        }
                    });
                });
            </script>
            """
            
            # 将自定义控制器添加到地图
            custom_control = folium.Element(custom_control_html)
            m.get_root().html.add_child(custom_control)

    # 添加热力图显示环境参数强度
    heatmap_data = []
    for node_id, node in graph.nodes.items():
        if node.node_type == "Environment":
            location = node.attributes.get("Location")
            if location:
                try:
                    lon, lat = map(float, location.split(","))
                    values = node.attributes.get("Value", {})
                    for env_type, value in values.items():
                        try:
                            # 尝试将值转换为浮点数
                            numeric_value = float(value)
                            # 添加位置和值的三元组
                            heatmap_data.append([lat, lon, numeric_value])
                        except (ValueError, TypeError):
                            # 如果值不是数字，跳过
                            continue
                except Exception as e:
                    print(f"处理热力图数据出错 {node_id}: {e}")
                    continue
    
    if heatmap_data:
        try:
            heatmap_layer = folium.FeatureGroup(name="环境参数热力图")
            HeatMap(heatmap_data).add_to(heatmap_layer)
            heatmap_layer.add_to(m)
        except Exception as e:
            print(f"创建热力图出错: {e}")
    
    # 添加所有图层到地图
    equipment_layer.add_to(m)
    for env_type, env_layer in environment_layers.items():
        env_layer.add_to(m)
    
    # 添加图层控制
    folium.LayerControl(collapsed=False).add_to(m)
    
    # 添加全屏控制
    try:
        Fullscreen().add_to(m)
    except Exception as e:
        print(f"添加全屏控制失败: {e}")
    
    # 添加测量工具
    try:
        MeasureControl(position='topleft', primary_length_unit='kilometers').add_to(m)
    except Exception as e:
        print(f"添加测量工具失败: {e}")
    
    # 保存地图
    try:
        m.save(filename)
        print(f"已保存可视化地图到: {filename}")
        
    except Exception as e:
        print(f"保存地图文件失败: {e}")
    
    return m, graph_series, timestamps


def visualize_network_graph(graph, filename="scene_graph_network.html", filter_min_weight=None):
    """
    创建场景图的网络可视化
    
    :param graph: SceneGraph对象
    :param filename: 输出的HTML文件名
    :param filter_min_weight: 可选，过滤低于此权重的边
    :return: None
    """
    try:
        import networkx as nx
        from pyvis.network import Network
    except ImportError:
        print("请安装所需包: pip install networkx pyvis")
        return None
    
    # 确保输出目录存在
    output_dir = os.path.dirname(filename)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # 创建NetworkX图
    G = nx.DiGraph()
    
    # 添加节点
    for node_id, node in graph.nodes.items():
        node_type = node.node_type
        node_name = node.attributes.get('Name', node_id)
        
        # 为不同类型节点设置不同颜色
        node_color = "#1f77b4"  # 默认蓝色
        if node_type == "Equipment":
            node_color = "#ff7f0e"  # 橙色
        elif node_type == "Environment":
            env_type = node.attributes.get('Name', '')
            if env_type == "锋面":
                node_color = "#d62728"  # 红色
            elif env_type == "风暴增水":
                node_color = "#ff9896"  # 浅红色
            elif env_type == "中尺度涡":
                node_color = "#2ca02c"  # 绿色
        
        # 构建节点标题（悬停文本）
        title = f"{node_name} ({node_type})"
        if "Value" in node.attributes:
            values = node.attributes["Value"]
            value_text = ", ".join(f"{k}: {v}" for k, v in values.items())
            title += f"\n值: {value_text}"
        
        # 添加节点
        G.add_node(node_id, label=node_name, title=title, color=node_color, group=node_type)
    
    # 添加边
    for edge in graph.edges:
        # 如果设置了权重过滤，跳过低权重的边
        if filter_min_weight is not None and edge.weight < filter_min_weight:
            continue
        
        source_id = edge.source_node.node_id
        target_id = edge.target_node.node_id
        
        # 确定边颜色
        edge_color = "#999"  # 默认灰色
        if edge.edge_type == "NotCompatible":
            edge_color = "#d62728"  # 红色
        elif edge.edge_type == "Compatible":
            edge_color = "#2ca02c"  # 绿色
        
        # 创建边标题
        title = f"{edge.edge_type} (权重: {edge.weight:.2f})"
        if hasattr(edge, 'attributes') and "Reason" in edge.attributes:
            title += f"\n原因: {edge.attributes['Reason']}"
        
        # 添加边
        G.add_edge(
            source_id, 
            target_id, 
            title=title,
            color=edge_color,
            width=1 + min(5, 9 * edge.weight),  # 权重0对应宽度1，权重1对应宽度6
            label=f"{edge.weight:.2f}"
        )
    
    # 创建Pyvis网络
    net = Network(height="750px", width="100%", notebook=False, directed=True)
    
    # 配置选项
    net.set_options("""
    {
      "nodes": {
        "shape": "dot",
        "size": 20,
        "font": {
          "size": 14,
          "face": "Noto Sans CJK SC, sans-serif"
        },
        "borderWidth": 2,
        "shadow": true
      },
      "edges": {
        "smooth": {
          "enabled": true,
          "type": "dynamic"
        },
        "shadow": true,
        "arrows": {
          "to": {
            "enabled": true,
            "scaleFactor": 0.5
          }
        },
        "font": {
          "align": "middle"
        }
      },
      "physics": {
        "barnesHut": {
          "gravitationalConstant": -10000,
          "springConstant": 0.004,
          "springLength": 100
        },
        "stabilization": {
          "iterations": 1000
        }
      },
      "interaction": {
        "hover": true,
        "navigationButtons": true,
        "keyboard": true
      }
    }
    """)
    
    # 从NetworkX导入
    net.from_nx(G)
    
    # 保存到HTML
    try:
        net.save_graph(filename)
        print(f"已保存网络图到: {filename}")
        
        # 自动打开
        try:
            webbrowser.open('file://' + os.path.abspath(filename))
        except Exception as e:
            print(f"自动打开网络图失败: {e}")
    except Exception as e:
        print(f"保存网络图失败: {e}")
    
    return net

def visualize_all(graph, map_filename="scene_graph_map.html", network_filename="scene_graph_network.html", 
                 center_coordinate=None, filter_min_weight=None):
    """
    创建场景图的所有可视化（地图和网络图）
    
    :param graph: SceneGraph对象
    :param map_filename: 地图输出的HTML文件名
    :param network_filename: 网络图输出的HTML文件名
    :param center_coordinate: 可选，地图中心坐标
    :param filter_min_weight: 可选，过滤低于此权重的边
    :return: 生成的文件路径列表
    """
    results = []
    
    # 生成地图可视化
    try:
        map_result = visualize_scene_graph(
            graph, 
            filename=map_filename,
            center_coordinate=center_coordinate,
            filter_min_weight=filter_min_weight,
            auto_open=True
        )
        results.append(os.path.abspath(map_filename))
    except Exception as e:
        print(f"生成地图可视化失败: {e}")
    
    # 生成网络图可视化
    try:
        network_result = visualize_network_graph(
            graph,
            filename=network_filename,
            filter_min_weight=filter_min_weight
        )
        results.append(os.path.abspath(network_filename))
    except Exception as e:
        print(f"生成网络图可视化失败: {e}")
    
    return results

def quick_view(graph, center_coordinate=None, filter_min_weight=None):
    """
    快速查看场景图（创建临时文件并在浏览器中打开）
    
    :param graph: SceneGraph对象
    :param center_coordinate: 可选，地图中心坐标
    :param filter_min_weight: 可选，过滤低于此权重的边
    :return: 生成的文件路径列表
    """
    import tempfile
    
    # 创建临时目录
    temp_dir = tempfile.mkdtemp(prefix="scene_graph_")
    
    # 设置临时文件名
    map_filename = os.path.join(temp_dir, "map.html")
    network_filename = os.path.join(temp_dir, "network.html")
    
    # 生成可视化
    return visualize_all(
        graph,
        map_filename=map_filename,
        network_filename=network_filename,
        center_coordinate=center_coordinate,
        filter_min_weight=filter_min_weight
    )

def visualize_network_graph_plotly(graph, filename="scene_graph_network.html", filter_min_weight=None, 
                                   height=800, width=1000):
    """
    使用Plotly创建场景图的交互式网络可视化
    
    :param graph: SceneGraph对象
    :param filename: 输出的HTML文件名，如果为None则不保存
    :param filter_min_weight: 可选，过滤低于此权重的边
    :param show: 是否显示图形
    :param height: 图形高度(像素)
    :param width: 图形宽度(像素)
    :return: plotly figure对象
    """
    try:
        import networkx as nx
        import plotly.graph_objects as go
        import plotly.io as pio
        import numpy as np
        import os
        import tempfile
        import webbrowser
        
        # 设置默认渲染器为浏览器
        pio.renderers.default = "browser"
    except ImportError:
        print("请安装所需包: pip install networkx plotly numpy")
        return None
    
    # 如果指定了文件名，确保输出目录存在
    if filename:
        output_dir = os.path.dirname(filename)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
    
    # 创建NetworkX图
    G = nx.DiGraph()
    
    # 节点类型 -> 颜色映射
    node_color_map = {
        "Equipment": "#ff7f0e",  # 橙色
        "Environment": "#1f77b4"  # 蓝色
    }
    
    # 环境类型 -> 颜色映射
    env_color_map = {
        "锋面": "#d62728",     # 红色
        "风暴增水": "#ff9896", # 浅红色
        "中尺度涡": "#2ca02c"  # 绿色
    }
    
    # 添加节点
    node_names = {}  # 用于后续标签显示
    for node_id, node in graph.nodes.items():
        node_type = node.node_type
        node_name = node.attributes.get('Name', node_id)
        node_names[node_id] = node_name
        
        # 设置节点大小
        node_size = 25 if node_type == "Equipment" else 15
        
        # 为不同类型节点设置不同颜色
        if node_type == "Equipment":
            node_color = node_color_map["Equipment"]
        elif node_type == "Environment":
            env_type = node.attributes.get('Name', '')
            node_color = env_color_map.get(env_type, node_color_map["Environment"])
        else:
            node_color = "#1f77b4"  # 默认蓝色
        
        # 构建节点悬停文本
        hover_text = f"ID: {node_id}<br>名称: {node_name}<br>类型: {node_type}"
        if "Value" in node.attributes:
            values = node.attributes["Value"]
            for key, value in values.items():
                hover_text += f"<br>{key}: {value}"
        
        # 添加节点
        G.add_node(
            node_id, 
            name=node_name, 
            color=node_color, 
            size=node_size, 
            type=node_type,
            hover=hover_text
        )
    
    # 边类型 -> 颜色映射
    edge_color_map = {
        "NotCompatible": "#d62728",  # 红色
        "Compatible": "#2ca02c",     # 绿色
        "default": "#999"            # 灰色
    }
    
    # 添加边
    for edge in graph.edges:
        # 如果设置了权重过滤，跳过低权重的边
        if filter_min_weight is not None and edge.weight < filter_min_weight:
            continue
        
        source_id = edge.source_node.node_id
        target_id = edge.target_node.node_id
        
        # 确定边颜色
        edge_color = edge_color_map.get(edge.edge_type, edge_color_map["default"])
        
        # 构建边悬停文本
        hover_text = f"类型: {edge.edge_type}<br>权重: {edge.weight:.2f}"
        if hasattr(edge, 'attributes') and "Reason" in edge.attributes:
            hover_text += f"<br>原因: {edge.attributes['Reason']}"
        
        # 添加边
        G.add_edge(
            source_id, 
            target_id, 
            color=edge_color,
            width=1 + min(5, 9 * edge.weight),
            weight=edge.weight,
            type=edge.edge_type,
            hover=hover_text
        )
    
    # 使用spring布局计算节点位置
    pos = nx.spring_layout(G, seed=42, k=0.3, iterations=50)
    
    # 分离不同节点类型
    node_types = {}
    for node, attr in G.nodes(data=True):
        node_type = attr['type']
        if node_type not in node_types:
            node_types[node_type] = []
        node_types[node_type].append(node)
    
    # 创建Plotly图
    fig = go.Figure()
    
    # 添加每种类型的节点作为不同的轨迹
    for node_type, nodes in node_types.items():
        node_x = [pos[node][0] for node in nodes]
        node_y = [pos[node][1] for node in nodes]
        node_text = [node_names[node] for node in nodes]
        node_hover = [G.nodes[node]['hover'] for node in nodes]
        node_colors = [G.nodes[node]['color'] for node in nodes]
        node_sizes = [G.nodes[node]['size'] * 2 for node in nodes]  # 调整大小
        
        fig.add_trace(go.Scatter(
            x=node_x, 
            y=node_y,
            mode='markers+text',
            name=node_type,
            marker=dict(
                color=node_colors,
                size=node_sizes,
                line=dict(width=1, color='black')
            ),
            text=node_text,
            hovertext=node_hover,
            hoverinfo='text',
            textposition='bottom center',
            textfont=dict(size=10)
        ))
    
    # 分离不同类型的边
    edge_types = {}
    for u, v, attr in G.edges(data=True):
        edge_type = attr['type']
        edge_color = attr['color']
        
        # 使用类型和颜色组合作为key
        type_color_key = f"{edge_type}_{edge_color}"
        
        if type_color_key not in edge_types:
            edge_types[type_color_key] = {
                'type': edge_type,
                'color': edge_color,
                'edges': []
            }
        edge_types[type_color_key]['edges'].append((u, v, attr))
    
    # 添加每种类型和颜色的边
    for type_color_key, edge_data in edge_types.items():
        edge_type = edge_data['type']
        edge_color = edge_data['color']
        edges = edge_data['edges']
        
        # 处理同一颜色的边为一组
        edge_x = []
        edge_y = []
        edge_hovers = []
        edge_width = 0  # 将使用同一颜色边的平均宽度
        
        for u, v, attr in edges:
            # 更新边宽度（使用平均值）
            edge_width += attr['width']
            
            # 创建从源到目标的线条
            x0, y0 = pos[u]
            x1, y1 = pos[v]
            
            # 计算箭头的中间点和方向（略微偏移直线以避免重叠）
            length = np.sqrt((x1-x0)**2 + (y1-y0)**2)
            if length == 0:  # 防止自环
                continue
                
            # 添加一些随机偏移使多条边之间不重叠
            dx = x1 - x0
            dy = y1 - y0
            x2 = x0 + dx * 0.6 + dy * 0.03  # 控制点1
            y2 = y0 + dy * 0.6 - dx * 0.03  # 控制点1
            x3 = x0 + dx * 0.4 - dy * 0.03  # 控制点2 
            y3 = y0 + dy * 0.4 + dx * 0.03  # 控制点2
            
            # 添加点创建平滑曲线
            edge_x.extend([x0, x3, x2, x1, None])
            edge_y.extend([y0, y3, y2, y1, None])
            
            # 添加同样的悬停文本给每个线段点
            edge_hovers.extend([attr['hover']] * 5)
        
        if edges:  # 避免空的边组
            edge_width = edge_width / len(edges)  # 计算平均宽度
            
            fig.add_trace(go.Scatter(
                x=edge_x, 
                y=edge_y,
                mode='lines',
                name=edge_type,
                line=dict(
                    color=edge_color,
                    width=edge_width
                ),
                hovertext=edge_hovers,
                hoverinfo='text',
                opacity=0.7
            ))
    
    # 设置布局
    fig.update_layout(
        title=dict(
            text="海洋环境场景Graph",
            font=dict(size=20)
        ),
        showlegend=True,
        legend=dict(
            title=dict(text="图例"),
            x=0.01,
            y=0.99,
            bordercolor="black",
            borderwidth=1
        ),
        hovermode="closest",
        margin=dict(l=20, r=20, t=40, b=20),
        plot_bgcolor='rgb(248,248,248)',
        height=height,
        width=width,
        xaxis=dict(
            showgrid=False,
            zeroline=False,
            showticklabels=False
        ),
        yaxis=dict(
            showgrid=False,
            zeroline=False,
            showticklabels=False
        )
    )
    
    # 添加自定义按钮
    node_traces_idx = [i for i, trace in enumerate(fig.data) if trace.mode == 'markers+text']
    edge_traces_idx = [i for i, trace in enumerate(fig.data) if trace.mode == 'lines']
    
    fig.update_layout(
        updatemenus=[
            dict(
                type="buttons",
                direction="down",
                buttons=[
                    dict(
                        args=[{"visible": [True] * len(fig.data)}],
                        label="显示全部",
                        method="update"
                    ),
                    dict(
                        args=[{"visible": [i in node_traces_idx for i in range(len(fig.data))]}],
                        label="只显示节点",
                        method="update"
                    ),
                    dict(
                        args=[{"visible": [i in edge_traces_idx for i in range(len(fig.data))]}],
                        label="只显示关系",
                        method="update"
                    )
                ],
                pad={"r": 10, "t": 10},
                showactive=True,
                x=0.99,
                xanchor="right",
                y=0.05,
                yanchor="bottom"
            )
        ]
    )
    
    # 添加注释说明
    fig.add_annotation(
        text="点击节点或边查看详细信息",
        xref="paper", yref="paper",
        x=0.01, y=0.01,
        showarrow=False,
        font=dict(
            size=12,
            color="gray"
        )
    )
    
    # 如果指定了文件名，也保存到那里
    if filename:
        try:
            fig.write_html(filename, include_plotlyjs='cdn')
            print(f"已保存交互式网络图到: {filename}")
        except Exception as e:
            print(f"保存网络图失败: {e}")
    
    return fig


def visualize_dynamic_network(graph_series, timestamps, filename="dynamic_network.html", 
                           filter_min_weight=0.0, show=True, height=800, width=800):
    """
    创建随时间变化的动态场景图的交互式网络可视化
    
    :param graph_series: SceneGraph对象列表，每个代表一个时间点的图状态
    :param timestamps: 时间戳列表，与graph_sequence等长，表示每个图的时间点
    :param filename: 输出的HTML文件名，如果为None则不保存
    :param filter_min_weight: 可选，过滤低于此权重的边
    :param show: 是否显示图形
    :param height: 图形高度(像素)
    :param width: 图形宽度(像素)
    :return: 可视化对象
    """
    try:
        import networkx as nx
        import plotly.graph_objects as go
        import numpy as np
        import tempfile
        import webbrowser
        
        # 确保时间戳列表与图序列等长
        if len(timestamps) != len(graph_series):
            print(f"警告：时间戳数量({len(timestamps)})与图数量({len(graph_series)})不匹配")
            # 使用较短的列表长度
            min_len = min(len(timestamps), len(graph_series))
            timestamps = timestamps[:min_len]
            graph_series = graph_series[:min_len]
        
        # 收集所有图中的所有节点，以创建一致的布局
        all_nodes = set()
        for graph in graph_series:
            all_nodes.update(graph.nodes.keys())
        
        # 创建合并的NetworkX图以计算统一布局
        G_combined = nx.DiGraph()
        for node_id in all_nodes:
            G_combined.add_node(node_id)
        
        # 添加所有边的信息以影响布局
        for graph in graph_series:
            for edge in graph.edges:
                if edge.weight >= filter_min_weight:
                    source_id = edge.source_node.node_id
                    target_id = edge.target_node.node_id
                    # 如果边已存在，使用最大权重
                    if G_combined.has_edge(source_id, target_id):
                        current_weight = G_combined.edges[source_id, target_id]['weight']
                        G_combined.edges[source_id, target_id]['weight'] = max(current_weight, edge.weight)
                    else:
                        G_combined.add_edge(source_id, target_id, weight=edge.weight)
        
        # 计算统一布局
        pos = nx.spring_layout(G_combined, seed=42, k=0.3, iterations=50)
        
        # 节点类型 -> 颜色映射
        node_color_map = {
            "Equipment": "#ff7f0e",  # 橙色
            "Environment": "#1f77b4"  # 蓝色
        }
        
        # 环境类型 -> 颜色映射
        env_color_map = {
            "锋面": "#d62728",     # 红色
            "风暴增水": "#ff9896", # 浅红色
            "中尺度涡": "#2ca02c"  # 绿色
        }
        
        # 边类型 -> 颜色映射
        edge_color_map = {
            "NotCompatible": "#d62728",  # 红色
            "Compatible": "#2ca02c",     # 绿色
            "default": "#999"            # 灰色
        }
        
        # 创建每个时间点的帧
        frames = []
        
        # 为第一帧创建基本图形数据
        first_graph = graph_series[0]
        traces, node_traces_idx, edge_traces_idx = create_graph_traces(
            first_graph, pos, node_color_map, env_color_map, edge_color_map, filter_min_weight
        )
        
        # 创建Plotly图形
        fig = go.Figure(
            data=traces,
            layout=go.Layout(
                title=dict(
                    text=f"海洋环境与设备场景图 - {timestamps[0]}",
                    font=dict(size=20)
                ),
                showlegend=True,
                legend=dict(
                    title=dict(text="图例"),
                    x=0.01,
                    y=0.99,
                    bordercolor="black",
                    borderwidth=1
                ),
                hovermode="closest",
                margin=dict(l=20, r=20, t=40, b=20),
                plot_bgcolor='rgb(248,248,248)',
                height=height,
                width=width,
                xaxis=dict(
                    showgrid=False,
                    zeroline=False,
                    showticklabels=False,
                    range=[min(x for x, _ in pos.values()) - 0.2, max(x for x, _ in pos.values()) + 0.2]
                ),
                yaxis=dict(
                    showgrid=False,
                    zeroline=False,
                    showticklabels=False,
                    range=[min(y for _, y in pos.values()) - 0.2, max(y for _, y in pos.values()) + 0.2]
                ),
                updatemenus=[
                    # 播放控制按钮
                    dict(
                        type="buttons",
                        direction="right",
                        showactive=False,
                        x=0.1,
                        y=0,
                        xanchor="right",
                        yanchor="bottom",
                        buttons=[
                            dict(
                                label="播放",
                                method="animate",
                                args=[None, {"frame": {"duration": 800, "redraw": True}, "fromcurrent": True}]
                            ),
                            dict(
                                label="暂停",
                                method="animate",
                                args=[[None], {"frame": {"duration": 0, "redraw": True}, "mode": "immediate"}]
                            )
                        ]
                    ),
                    # 视图控制按钮
                    dict(
                        type="buttons",
                        direction="down",
                        buttons=[
                            dict(
                                args=[{"visible": [True] * len(traces)}],
                                label="显示全部",
                                method="update"
                            ),
                            dict(
                                args=[{"visible": [i in node_traces_idx for i in range(len(traces))]}],
                                label="只显示节点",
                                method="update"
                            ),
                            dict(
                                args=[{"visible": [i in edge_traces_idx for i in range(len(traces))]}],
                                label="只显示关系",
                                method="update"
                            )
                        ],
                        pad={"r": 10, "t": 10},
                        showactive=True,
                        x=0.99,
                        xanchor="right",
                        y=0.05,
                        yanchor="bottom"
                    )
                ],
                # 添加时间滑块
                sliders=[{
                    "active": 0,
                    "yanchor": "top",
                    "xanchor": "left",
                    "currentvalue": {
                        "font": {"size": 16},
                        "prefix": "时间: ",
                        "visible": True,
                        "xanchor": "right"
                    },
                    "transition": {"duration": 300, "easing": "cubic-in-out"},
                    "pad": {"b": 10, "t": 50},
                    "len": 0.9,
                    "x": 0.1,
                    "y": 0,
                    "steps": []
                }]
            )
        )
        
        # 添加注释说明
        fig.add_annotation(
            text="点击节点或边查看详细信息",
            xref="paper", yref="paper",
            x=0.01, y=0.01,
            showarrow=False,
            font=dict(
                size=12,
                color="gray"
            )
        )
        
        # 创建所有帧
        slider_steps = []
        
        for i, (graph, timestamp) in enumerate(zip(graph_series, timestamps)):
            frame_traces, _, _ = create_graph_traces(
                graph, pos, node_color_map, env_color_map, edge_color_map, filter_min_weight
            )
            
            frame = go.Frame(
                data=frame_traces,
                name=str(i),
                layout=go.Layout(title=f"海洋环境与设备场景图 - {timestamp}")
            )
            frames.append(frame)
            
            # 创建滑块步骤
            step = {
                "args": [
                    [str(i)],
                    {"frame": {"duration": 300, "redraw": True}, "mode": "immediate"}
                ],
                "label": timestamp if len(timestamp) < 15 else timestamp[:12] + "...",
                "method": "animate"
            }
            slider_steps.append(step)
        
        # 添加滑块步骤
        fig.layout.sliders[0].steps = slider_steps
        
        # 添加帧
        fig.frames = frames
        
        # 保存和显示图形
        if filename:
            try:
                fig.write_html(filename, include_plotlyjs='cdn')
                print(f"已保存动态网络图到: {filename}")
            except Exception as e:
                print(f"保存网络图失败: {e}")
        
        if show:
            # 使用临时文件和浏览器打开
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.html')
            temp_filename = temp_file.name
            temp_file.close()
            
            try:
                fig.write_html(temp_filename, include_plotlyjs='cdn')
                print(f"已创建临时文件: {temp_filename}")
                webbrowser.open('file://' + os.path.abspath(temp_filename))
            except Exception as e:
                print(f"打开浏览器失败: {e}")
                try:
                    fig.show()
                except Exception as e2:
                    print(f"直接显示也失败: {e2}")
        
        return fig
        
    except Exception as e:
        print(f"创建动态网络图失败: {e}")
        return None

def create_graph_traces(graph, pos, node_color_map, env_color_map, edge_color_map, filter_min_weight=0.0):
    """
    为给定的场景图创建Plotly轨迹
    
    :param graph: SceneGraph对象
    :param pos: 节点位置字典
    :param node_color_map: 节点类型颜色映射
    :param env_color_map: 环境类型颜色映射
    :param edge_color_map: 边类型颜色映射
    :param filter_min_weight: 过滤低于此权重的边
    :return: (traces, node_traces_idx, edge_traces_idx) 元组
    """
    try:
        import plotly.graph_objects as go
        import numpy as np
        
        # 准备跟踪列表和索引列表
        traces = []
        node_traces_idx = []
        edge_traces_idx = []
        
        # 按节点类型分组
        node_groups = {}
        for node_id, node in graph.nodes.items():
            node_type = node.node_type
            if node_type not in node_groups:
                node_groups[node_type] = []
            node_groups[node_type].append(node)
        
        # 添加节点轨迹
        for node_type, nodes in node_groups.items():
            node_x = []
            node_y = []
            node_text = []
            node_hover = []
            node_colors = []
            node_sizes = []
            
            for node in nodes:
                node_id = node.node_id
                if node_id not in pos:
                    continue  # 跳过位置未知的节点
                    
                # 获取节点位置
                x, y = pos[node_id]
                node_x.append(x)
                node_y.append(y)
                
                # 获取节点名称
                node_name = node.attributes.get('Name', node_id)
                node_text.append(node_name)
                
                # 创建悬停文本
                hover_text = f"ID: {node_id}<br>名称: {node_name}<br>类型: {node.node_type}"
                if "Value" in node.attributes:
                    values = node.attributes["Value"]
                    for key, value in values.items():
                        hover_text += f"<br>{key}: {value}"
                node_hover.append(hover_text)
                
                # 决定节点颜色
                if node.node_type == "Equipment":
                    node_color = node_color_map["Equipment"]
                elif node.node_type == "Environment":
                    env_name = node.attributes.get('Name', '')
                    node_color = env_color_map.get(env_name, node_color_map["Environment"])
                else:
                    node_color = "#1f77b4"  # 默认蓝色
                node_colors.append(node_color)
                
                # 决定节点大小
                node_size = 25 if node.node_type == "Equipment" else 15
                node_sizes.append(node_size * 2)  # 乘以2使其更明显
            
            # 只有当有节点时才添加轨迹
            if node_x:
                node_traces_idx.append(len(traces))
                traces.append(go.Scatter(
                    x=node_x, 
                    y=node_y,
                    mode='markers+text',
                    name=node_type,
                    marker=dict(
                        color=node_colors,
                        size=node_sizes,
                        line=dict(width=1, color='black')
                    ),
                    text=node_text,
                    hovertext=node_hover,
                    hoverinfo='text',
                    textposition='bottom center',
                    textfont=dict(size=10)
                ))
        
        # 按边类型和颜色分组
        edge_groups = {}
        for edge in graph.edges:
            # 过滤低权重的边
            if edge.weight < filter_min_weight:
                continue
                
            # 获取源和目标节点ID
            source_id = edge.source_node.node_id
            target_id = edge.target_node.node_id
            
            # 确保两个节点都有位置
            if source_id not in pos or target_id not in pos:
                continue
                
            # 获取边类型和颜色
            edge_type = edge.edge_type
            edge_color = edge_color_map.get(edge_type, edge_color_map["default"])
            
            # 创建组键
            group_key = f"{edge_type}_{edge_color}"
            if group_key not in edge_groups:
                edge_groups[group_key] = {
                    'type': edge_type,
                    'color': edge_color,
                    'edges': []
                }
            edge_groups[group_key]['edges'].append(edge)
        
        # 添加边轨迹
        for group_key, group_data in edge_groups.items():
            edge_type = group_data['type']
            edge_color = group_data['color']
            edges = group_data['edges']
            
            edge_x = []
            edge_y = []
            edge_hover = []
            total_width = 0
            
            for edge in edges:
                source_id = edge.source_node.node_id
                target_id = edge.target_node.node_id
                
                # 获取节点位置
                x0, y0 = pos[source_id]
                x1, y1 = pos[target_id]
                
                # 计算边宽度
                edge_width = 1 + min(5, 9 * edge.weight)
                total_width += edge_width
                
                # 创建平滑曲线
                dx = x1 - x0
                dy = y1 - y0
                
                # 添加偏移以避免重叠
                x2 = x0 + dx * 0.6 + dy * 0.03  # 控制点1
                y2 = y0 + dy * 0.6 - dx * 0.03  # 控制点1
                x3 = x0 + dx * 0.4 - dy * 0.03  # 控制点2 
                y3 = y0 + dy * 0.4 + dx * 0.03  # 控制点2
                
                # 将曲线点添加到列表
                edge_x.extend([x0, x3, x2, x1, None])
                edge_y.extend([y0, y3, y2, y1, None])
                
                # 创建悬停文本
                hover_text = f"类型: {edge.edge_type}<br>权重: {edge.weight:.2f}"
                if "Reason" in edge.attributes:
                    hover_text += f"<br>原因: {edge.attributes['Reason']}"
                
                # 为每个点段添加相同的悬停文本
                edge_hover.extend([hover_text] * 5)
            
            # 只有当有边时才添加轨迹
            if edge_x:
                # 计算平均宽度
                avg_width = total_width / len(edges) if edges else 1
                
                edge_traces_idx.append(len(traces))
                traces.append(go.Scatter(
                    x=edge_x, 
                    y=edge_y,
                    mode='lines',
                    name=edge_type,
                    line=dict(
                        color=edge_color,
                        width=avg_width
                    ),
                    hovertext=edge_hover,
                    hoverinfo='text',
                    opacity=0.7
                ))
        
        return traces, node_traces_idx, edge_traces_idx
    except Exception as e:
        print(f"创建图形轨迹失败: {e}")
        return [], [], []
