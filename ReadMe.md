# TCP端口转发
> 基于使用远程桌面的需求，通过在路由器配置了DDNS以及端口映射，已经可以实现在家中远程桌面连接到公司的电脑。接下来打算反过来远程桌面连接（公司电脑远程桌面连接到自己的电脑），但问题来了，公司是有公网IP的，而自己家中并没有公网IP，所以DDNS那套没办法行得通了，搜索了一通，大概得到的方案就是使用类似一些远程控制的软件（如TeamViewer，向日葵之类的），但这类远程控制的软件诸多限制（限速、收费等等），而且本人(穷)还想直接用Windows的远程桌面连接，想了想决定自己写个端口转发程序，然后通过公司的DDNS提供的地址访问自己的电脑，并且外部访问公司的主机时可以自行指定目标的地址和端口。

## 功能简述
- ### 个人主机访问公司主机
  - 服务器运行服务程序
  - 个人主机运行用户端程序，通过访问本机地址可以访问到公司主机的地址
- ### 公司主机访问个人主机
  - 服务器运行服务程序
  - 个人主机运行客户端程序
  - 公司主机可以通过服务器地址访问到个人主机的地址
  
## 初始定义说明
- 局域网A（服务器所在局域网）
  - 服务器A0: 192.168.1.2 (绑定了域名 xxx.yyy.cn，公网可访问)
  - 主机A1: 192.168.1.100
  - 主机A2: 192.168.1.200
- 局域网B（用户B所在局域网）
  - 主机B1: 192.168.2.66
  - 主机B2: 192.168.2.88
- 局域网C（用户C所在局域网）
  - 主机C1: 192.168.3.33
  - 主机C2: 192.168.3.99

1. 局域网之间无法直接通信
2. 局域网内主机可以直接通信
3. 域名xxx.yyy.cn公网可访问，即所有主机都可以直接访问
4. 以下服务器用到的端口假定都已开放
   
## 使用场景（以Windows的远程桌面为例）
- ### 主机B1远程桌面到主机A2
  - #### 方法一: 通过服务器A0的10086端口访问(服务器启动时固定访问的目标地址和端口)
    - 服务器A0
        ```bash
        python3 tcp_forwarding.py --bind_host=0.0.0.0 --bind_port=10086 --target_host=192.168.1.200 --target_port=3389
        ```
    - 主机B1连接地址: xxx.yyy.cn:10086
  
  - #### 方法二：通过主机B1的10086端口访问(控制端可以自行指定目标的地址和端口)
    - 服务器A0
        ```bash
        python tcp_forwarding_user_server.py --bind_host=0.0.0.0 --bind_port=22222
        ```
    - 主机B1
        ```bash
        python tcp_forwarding_user_client.py --server_host=xxx.yyy.cn --server_port=22222 --bind_host=0.0.0.0 --bind_port=10086 --server_target_host=192.168.1.200 --server_target_port=3389
        ```
    - 主机B1连接地址: localhost:10086
  
- ### 主机A1远程桌面到主机B2（通过服务器的10086端口访问）
  - 服务器A0
    ```bash
    python tcp_forwarding_multi_server.py --bind_host=0.0.0.0 --bind_port=33333
    或者
    python tcp_forwarding_multi_server_select.py --bind_host=0.0.0.0 --bind_port=33333
    ```
  - 主机B2
    ```bash
    python tcp_forwarding_multi_client.py --server_host=xxx.yyy.cn --server_port=33333 --target_host=localhost --target_port=3389 --server_target_port=10086
    ```
  - 主机A1连接地址: xxx.yyy.cn:10086


## 功能实现
- ### 本机端口转发：将本机端口转发到另一个地址的某个端口
    ```bash
    python3 tcp_forwarding.py --bind_host=0.0.0.0 --bind_port=10086 --target_host=192.168.1.200 --target_port=3389
    ```  
    1. 监听本机地址(bind_host, bind_port)，等待连接
    2. 一旦有连接S1，创建连接S2连接到目标地址(targer_host, target_port)
    3. 相互转发S1和S2两个连接的数据

- ### 通过访问本机的某些端口来达到访问服务器所能访问的地址
    #### 服务器 
    ```bash
    python3 tcp_forwarding_user_server.py --bind_host=0.0.0.0 --bind_port=22222
    ```
    1. 监听本机地址(bind_host, bind_port)，等待连接
    2. 一旦有连接S1，从S1接收目标地址(ADDR)
    3. 创建连接S2连接目标地址ADDR(server_target_host, server_target_port)，通过S1发送反馈
    4. 相互转发S1和S2两个连接的数据
   
    #### 用户端(主控端) 
    ```bash
    python3 tcp_forwarding_user_client.py --bind_host=0.0.0.0 --bind_port=10086 --server_host=xxx.yyy.cn --server_port=22222 --server_target_host=192.168.1.200 --server_target_port=3389
    ```
    1. 监听本机地址(bind_host, bind_port)，等待连接
    2. 一旦有连接S1，就创建连接S2连接到(server_host, server_port)，并通过S2发送目标地址给服务器
    3. S2接收服务器发来的反馈
    4. 相互转发S1和S2两个连接的数据

- ### 通过访问服务器某些端口来访问到客户端的地址
    #### 服务器
    ```bash
    python3 tcp_forwarding_multi_server.py --bind_host=0.0.0.0 --bind_port=33333
    ```
    1. 监听本机地址(bind_host, bind_port)，等待连接
    2. 一旦有连接S1，从S1接收目标地址ADDR
    3. 监听本机地址ADDR(0.0.0.0, server_target_port)，等待连接
    4. 一旦有连接S2，通过S1发送反馈
    5. 相互转发S1和S2两个连接的数据

    #### 客户端(受控端) 
    ```bash
    python3 tcp_forwarding_multi_client.py --server_host=xxx.yyy.cn --server_port=33333 --target_host=localhost --target_port=3389 --server_target_port=10086
    ```
    1. 创建连接S1连接服务器地址(server_host, server_port)，并发送地址ADDR(0.0.0.0, server_target_port)信息
    2. S1接收服务器发来的反馈
    3. 创建连接S2连接目标地址(target_host, target_port)
    4. 相互转发S1和S2两个连接的数据

