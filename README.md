<p align="center">
    <img src="assets/logo/logo.png" alt="Logo" width="156" height="156">
</p>

<div align="center">

# Contrail

简单易用的服务器资源和计算平台监控工具

</div>

<p align="center">
    <a href="#主要功能">✨ 主要功能</a>&nbsp;&nbsp;|&nbsp;&nbsp;
    <a href="#部署方式">⚙️ 部署方式</a>&nbsp;&nbsp;|&nbsp;&nbsp;
    <a href="#使用说明">📖 使用说明</a>
    <br />
    <br />
</p>


![overview](assets/img/overview_light.png#gh-light-mode-only)
![overview](assets/img/overview_dark.png#gh-dark-mode-only)


Contrail 是一个简单易用的服务器资源和计算平台监控工具。它旨在提供一个高效、直观的监控界面，帮助用户了解各个系统的实时和历史状态。

### 使用技术

- 网页搭建：`Python` + [`streamlit`](https://streamlit.io/)
- 数据可视化：[`altair`](https://altair-viz.github.io/) + [`plotly`](https://plotly.com/)
- GPU 监控记录：`nvidia-ml-py` + `sqlite3`
- AI4S 数据收集：[`selenuim`](https://www.selenium.dev/)

## 主要功能

### 服务器资源监控

#### GPU 实时状态

<details>
<summary>点击展开图像</summary>

![realtime monitor](assets/gif/realtime_light.gif#gh-light-mode-only)
![realtime monitor](assets/gif/realtime_dark.gif#gh-dark-mode-only)

</details>


#### GPU 历史信息

<details>
<summary>点击展开图像</summary>

![history monitor](assets/gif/history_light.gif#gh-light-mode-only)
![history monitor](assets/gif/history_dark.gif#gh-dark-mode-only)

</details>


### AI4S 平台监控

#### AI4S 任务列表

<details>
<summary>点击展开图像</summary>

![ai4s tasks](assets/img/ai4s_task_light.png#gh-light-mode-only)
![ai4s tasks](assets/img/ai4s_task_dark.png#gh-dark-mode-only)

</details>


#### AI4S 费用记录

<details>
<summary>点击展开图像</summary>

![ai4s fee](assets/img/ai4s_fee_light.png#gh-light-mode-only)
![ai4s fee](assets/img/ai4s_fee_dark.png#gh-dark-mode-only)

</details>


## 部署方式

### 主设备

根据需要运行的监控项目安装对应的依赖：

```bash
pip install -e .[ai4s,web]
```

同时在 `config/host_config.json` 中配置主设备的相关信息。


### 主设备 - AI4S

> [!NOTE]
> ai4s 未来也会提供配置文件模板，因此AI4S相关命令仅为临时方案

获取 cookies：

```bash
python -m contrail.ai4s.ai4s_login --url http://aiplatform.ai4s.sjtu.edu.cn/bml/project/...
```

然后在 `screenshoots/body.png` 下查看验证码和动态口令二维码

> [!NOTE]
> TODO：chromedriver 的路径未来将会由配置文件提供

将与浏览器对应的 chromedriver 放在 `resource/chromedriver` 下。


### socket 设备

仅需安装基本的依赖：

```bash
pip install -e .
```

同时在 `config/sender_config.json` 中配置相关信息。


## 使用说明

### 主设备

启动 web 应用：

```bash
streamlit run webapp.py --server.port 3333
```

启动监控：

```bash
contrail monitor
```

在运行过程中：

```bash
list                  # 列出所有被监控的设备
remove <device_name>  # 移除被监控的设备
reload                # 重新加载配置文件
exit                  # 退出监控
```

例如，若需要更新已有设备的配置，可以直接修改 `config/host_config.json` 中的相关信息，然后运行：

```bash
remove <device_name>
reload
```

### 主设备 - AI4S


运行监控：

```bash
python -m contrail.ai4s.ai4s_execute --url http://aiplatform.ai4s.sjtu.edu.cn/bml/project/model-train/notebook/...
```

### socket 设备

连接到主设备

```bash
contrail sender
```