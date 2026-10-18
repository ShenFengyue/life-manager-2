# -*- coding: utf-8 -*-
"""为产品演示视频生成一份「用了一年多」的示例数据。

特点：
- 全部通过 `LifeManagerService` 写入，归属快照、历史事件、关联、置顶都由程序自己生成；
- 时间线从 START 一路铺到今天，工作日多、周末少，中间有出差、休假、发布冲刺、生病休整；
- 节点的重命名、移动、归档都发生在真实日期上，所以「变化历史」不是空的；
- 顺手写约两百天日记、几条标语历史，方便演示左栏那一块。

用法（会把现有 data/ 数据库清掉重建，请勿在正式数据上跑）：
    .venv\\Scripts\\python.exe tools\\seed_demo.py --force
"""

from __future__ import annotations

import argparse
import random
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import clock, diary, paths  # noqa: E402
from app.models import NodeType, Status  # noqa: E402
from app.services import LifeManagerService  # noqa: E402
from app.storage import Database  # noqa: E402

START = date(2025, 7, 1)
# 7 月 1 日只建立了结构，第一条记录从 7 月 3 日开始 —— 和日记里「从今天起」对得上。
ACTIVITY_START = START + timedelta(days=2)
TODAY = clock.now().date()
END = TODAY - timedelta(days=1)


def d(text: str) -> date:
    return date.fromisoformat(text)


# ------------------------------------------------------------------ 结构
TREE = (
    {
        "name": "AI Infra · 主业",
        "processes": (
            {
                "name": "推理调度器",
                "desc": "P99 < 400ms，利用率 75%",
                "next": "把 batch 调度改成 token 级抢占，先跑一版基线",
                "threads": (
                    {"name": "调度器重构", "weight": 10,
                     "next": "灰度 20% 流量，盯一晚上 P99"},
                    {"name": "KV Cache 与显存", "weight": 6,
                     "next": "把 block 回收日志接到看板"},
                    {"name": "延迟压测与 SLO", "weight": 5,
                     "next": "补一组 32k 上下文的压测"},
                ),
            },
            {
                "name": "模型服务化",
                "desc": "vLLM + K8s 多机集群",
                "next": "把新版本引擎推上预发",
                "threads": (
                    {"name": "vLLM 集成", "weight": 4,
                     "next": "跟进上游 PR 的 review"},
                    {"name": "多机部署", "weight": 3, "window": ("2026-04-01", None),
                     "next": "调通 RDMA 的拓扑感知"},
                ),
            },
            {
                "name": "技术领导",
                "desc": "带 6 人的 infra 小组",
                "next": "下周的 Q4 规划会先出草稿",
                "threads": (
                    {"name": "招聘与面试", "weight": 2, "window": ("2025-11-01", None),
                     "next": "把最后一轮面试排进来"},
                    {"name": "一对一与团队成长", "weight": 3,
                     "next": "整理这轮 1:1 的共同阻塞点"},
                    {"name": "季度规划", "weight": 1.5,
                     "next": "把 roadmap 拆成 6 周里程碑"},
                ),
            },
        ),
    },
    {
        "name": "影响力 · 对外输出",
        "processes": (
            {
                "name": "技术写作",
                "desc": "每月一篇长文",
                "next": "下一篇写调度器里的三个取舍",
                "threads": (
                    {"name": "博客长文", "initial": "个人博客", "weight": 4,
                     "next": "把压测图表重画一版"},
                    {"name": "内部技术文档", "weight": 2,
                     "next": "补失败路径那一节"},
                    {"name": "旧博客迁移", "initial": "旧站迁移", "weight": 2,
                     "window": ("2025-07-01", "2025-08-20")},
                ),
            },
            {
                "name": "演讲与社区",
                "next": "确认大会的最终版 slides",
                "threads": (
                    {"name": "会议演讲", "weight": 1.5,
                     "next": "排练第三遍，砍到 18 分钟"},
                    {"name": "开源项目", "weight": 4,
                     "next": "把 Windows 上的路径问题修掉"},
                    {"name": "英语表达", "weight": 2, "hours": (7, 9),
                     "next": "每天跟读 20 分钟"},
                ),
            },
            {
                "name": "播客",
                "desc": "两周一期，聊推理成本",
                "next": "下期嘉宾的时间还没定",
                "threads": (
                    {"name": "播客录制", "weight": 1, "window": ("2025-07-01", "2026-06-12")},
                ),
            },
        ),
    },
    {
        "name": "学习 · 长期复利",
        "processes": (
            {
                "name": "论文与系统阅读",
                "desc": "每周两篇，做卡片笔记",
                "next": "把 speculative decoding 那条线读完",
                "threads": (
                    {"name": "LLM 推理前沿", "weight": 4,
                     "next": "读 Mooncake 的调度部分"},
                    {"name": "分布式系统", "weight": 2.5,
                     "next": "重读 Raft 的成员变更"},
                    {"name": "数学与概率", "weight": 2,
                     "next": "把 KL 散度的推导自己写一遍"},
                ),
            },
            {
                "name": "工程手艺",
                "next": "用 Rust 写个小工具练手",
                "threads": (
                    {"name": "Rust", "weight": 3,
                     "next": "把 tokio 的 select 用熟"},
                    {"name": "数据库内核", "weight": 1.5,
                     "next": "把 LSM 的写放大算一遍"},
                ),
            },
        ),
    },
    {
        "name": "身体 · 能量管理",
        "processes": (
            {
                "name": "力量训练",
                "desc": "5×5 周期，周二/周五",
                "next": "深蹲加到 110kg 试试",
                "threads": (
                    {"name": "下肢力量", "weight": 3, "hours": (7, 9),
                     "next": "下周把深蹲加 2.5kg"},
                    {"name": "上肢与核心", "weight": 3, "hours": (18, 20),
                     "next": "引体向上冲 12 个"},
                ),
            },
            {
                "name": "耐力训练",
                "desc": "周跑量 35–50 km，Zone 2",
                "next": "周日长距离 18km",
                "threads": (
                    {"name": "晨跑", "weight": 6, "hours": (6, 8),
                     "next": "把周跑量稳在 45km"},
                    {"name": "半马备赛", "weight": 1.2, "hours": (6, 8),
                     "window": ("2025-07-01", "2025-11-16"),
                     "initial": "半马备赛"},
                ),
            },
            {
                "name": "恢复",
                "next": "这周争取 23:30 前睡",
                "threads": (
                    {"name": "睡眠", "weight": 2, "hours": (22, 23),
                     "next": "睡前半小时不看屏幕"},
                    {"name": "冥想与呼吸", "weight": 2, "hours": (22, 23),
                     "next": "把 4-7-8 呼吸固定下来"},
                ),
            },
        ),
    },
    {
        "name": "关系 · 支撑系统",
        "processes": (
            {
                "name": "家人",
                "next": "周末和爸妈视频",
                "threads": (
                    {"name": "父母", "weight": 1, "hours": (19, 21),
                     "next": "问问体检结果"},
                    {"name": "伴侣", "weight": 2, "hours": (19, 22),
                     "next": "把下个月的短假定下来"},
                ),
            },
            {
                "name": "朋友与社群",
                "next": "约一次周末爬山",
                "threads": (
                    {"name": "湾区朋友", "weight": 1.5, "hours": (11, 21),
                     "next": "回一下 Kevin 的消息"},
                    {"name": "行业交流", "weight": 1, "hours": (17, 21),
                     "next": "下个月的 meetup 报名"},
                ),
            },
        ),
    },
    {
        "name": "资产 · 财务",
        "processes": (
            {
                "name": "现金流",
                "desc": "储蓄率目标 45%",
                "next": "月底把这季度的账对一遍",
                "threads": (
                    {"name": "储蓄率复盘", "weight": 1, "hours": (21, 23),
                     "next": "砍掉两个不用的订阅"},
                    {"name": "股权与 vesting", "weight": 0.6, "hours": (21, 23),
                     "next": "确认下季度 vesting 日期"},
                ),
            },
            {
                "name": "投资",
                "desc": "被动为主，季度再平衡",
                "next": "十月的定投照旧",
                "threads": (
                    {"name": "指数定投", "weight": 0.8, "hours": (9, 12),
                     "next": "设置自动定投"},
                    {"name": "组合再平衡", "weight": 0.4, "hours": (21, 23),
                     "next": "算一下当前股债比例"},
                ),
            },
        ),
    },
    {
        "name": "创造 · 自己的产品",
        "processes": (
            {
                "name": "独立产品 Memex",
                "initial": "Side Project",
                "desc": "给研究者的知识库，Q1 上线",
                "next": "把导入流程做顺，再找 5 个人内测",
                "threads": (
                    {"name": "MVP 开发", "weight": 5, "hours": (21, 23),
                     "window": ("2026-01-12", None),
                     "next": "修同步的竞态，然后发内测"},
                    {"name": "用户访谈", "weight": 2, "hours": (10, 18),
                     "window": ("2026-02-01", None),
                     "next": "把这周的访谈整理成三条结论"},
                ),
            },
            {
                "name": "写作与表达",
                "next": "写第 12 期",
                "threads": (
                    {"name": "Newsletter", "weight": 1.5, "hours": (21, 23),
                     "window": ("2025-09-01", None),
                     "next": "定个每周四发的节奏"},
                ),
            },
        ),
    },
    {
        "name": "生活 · 体验",
        "processes": (
            {
                "name": "旅行",
                "next": "把年底的行程定下来",
                "threads": (
                    {"name": "日本行", "weight": 1, "hours": (9, 21),
                     "window": ("2025-12-15", "2026-01-05")},
                    {"name": "湾区徒步", "weight": 1.5, "hours": (7, 12),
                     "next": "找一条 12km 的路线"},
                ),
            },
            {
                "name": "居住",
                "next": "把书架装完",
                "threads": (
                    {"name": "公寓布置", "weight": 0.8, "hours": (10, 18)},
                ),
            },
        ),
    },
)


# ------------------------------------------------------------------ 备注
NOTE_BANK: dict[str, tuple[str, ...]] = {
    "调度器重构": (
        "把 batch 拼接从固定窗口改成 token 级抢占，P99 掉到 {ms}ms",
        "重写调度队列，去掉两把锁，吞吐 +{pct}%",
        "和 SRE 对齐 backpressure 策略，超时率从 {pct}% 降到 {pct2}%",
        "调 chunked prefill 的边界 case，找到一处 off-by-one",
        "review 同事的调度器 PR，提了 {n} 条意见",
        "把调度策略做成可插拔，方便后面试 priority / SJF",
        "补了 {n} 个单测覆盖抢占路径",
        "线上灰度 {pct}% 流量，观察 4 小时无异常",
        "把一个全局锁换成 per-shard，争用下来了",
        "画了一版调度时序图，理清了 prefill 和 decode 的交错",
    ),
    "KV Cache 与显存": (
        "PagedAttention 的 block 回收改成 LIFO，碎片率降到 {pct}%",
        "定位一次显存泄漏：CUDA graph 没释放",
        "prefix cache 命中率从 {pct}% 提到 {pct2}%",
        "算了 {n} 组参数下 KV cache 的理论上限",
        "和硬件团队对了一遍 HBM 带宽的数字",
        "写了个小工具 dump 每个 block 的引用计数",
        "把 block size 从 16 试到 64，最后选 32",
        "长上下文场景下显存告急，加了一版 offload 兜底",
    ),
    "延迟压测与 SLO": (
        "跑了一轮 {n}k 并发压测，P99 {ms}ms",
        "压测脚本搬进 nightly，早上自动出报告",
        "建了延迟拆解看板：prefill / decode / queue 三段",
        "tail latency 来自 batch padding，改小后 -{pct}%",
        "和产品确认 SLO：首 token < {ms}ms",
        "补了一组 32k 上下文的压测数据",
        "复现了一个只在跨机场景出现的长尾",
    ),
    "vLLM 集成": (
        "把 vLLM 升到新版本，修了 {n} 处 API 变更",
        "自定义 scheduler 接进 vLLM 的 engine，端到端跑通",
        "对比 vLLM 和 TensorRT-LLM 在长上下文下的表现",
        "读 vLLM 源码，理清 continuous batching 的实现",
        "给 vLLM 提了个 PR，被合进去了",
        "处理一个 KV cache 复用的兼容问题",
    ),
    "多机部署": (
        "在 {n} 台 H100 上跑通 Ray 集群",
        "调 K8s 的 GPU 拓扑感知，NVLink 利用率上去了",
        "写部署的 helm chart，顺手补了 values 注释",
        "处理一次节点重启导致的 KV cache 冷启动",
        "和平台组对网络方案：RDMA 比 TCP 快 {pct}%",
        "把镜像从 8G 压到 3G",
    ),
    "招聘与面试": (
        "面了 {n} 个候选人，重点看系统设计",
        "更新面试题库，加了一道推理调度题",
        "和 HR 对 offer 的级别",
        "写了一版面试反馈模板，全组统一用",
        "和一个候选人聊了两小时，最后决定要",
    ),
    "一对一与团队成长": (
        "和 {n} 个人做了 1:1，重点聊阻塞点",
        "帮同事梳理了他的项目路线",
        "给团队写了一份 oncall 手册",
        "复盘上次事故，明确了 {n} 条 action item",
        "把自己的工作拆出去两块，让两个人独立带",
        "和一位同事聊了他的晋升材料",
    ),
    "季度规划": (
        "写 Q{n} OKR 草稿",
        "和老板对齐了 headcount",
        "把 roadmap 拆成 6 周一个里程碑",
        "给全组讲了这季度的优先级",
        "砍掉了两个做不完的需求，只留三个",
    ),
    "博客长文": (
        "写了 {words} 字，关于推理调度的取舍",
        "改了三遍开头，最后从一次线上事故切入",
        "补了一组压测数据，图表重画",
        "发了《{title}》，收到 {n} 条讨论",
        "整理读者反馈，记下 {n} 个可以展开的点",
        "把一篇草稿删掉一半，反而清楚了",
        "读者来信问细节，补写了一段附录",
    ),
    "内部技术文档": (
        "把调度器的设计文档补完",
        "画了一版架构图，标出失败路径",
        "写了事故复盘的初稿",
        "给新人写了上手路径，从跑通 demo 开始",
        "把散在 chat 里的结论收进 wiki",
    ),
    "旧博客迁移": (
        "导出了老博客的 {n} 篇文章",
        "修了一批失效的图片链接",
        "把旧文章按主题重新归类",
    ),
    "会议演讲": (
        "写 talk 提纲，{n} 页",
        "排练两遍，砍掉三分之一内容",
        "在 {conf} 讲完，Q&A 很热",
        "会后有 {n} 个人来聊合作",
        "重做了一版 demo，现场跑通了",
    ),
    "开源项目": (
        "合了 {n} 个社区 PR",
        "补了 README 和 quickstart",
        "修了一个 Windows 上的路径 bug",
        "发了 v0.{n} 版本",
        "回了 {n} 个 issue，把常见问题写进 FAQ",
        "有公司来问能不能商用，回了一封长邮件",
    ),
    "英语表达": (
        "跟读 {min} 分钟 TED",
        "写了 {words} 词的英文摘要",
        "和湾区同事练了一小时口语",
        "背了 {n} 个技术表达",
        "把一篇中文讲稿自己译成英文",
    ),
    "播客录制": (
        "录了一期，聊推理成本",
        "剪了 {min} 分钟音频",
        "约了下期嘉宾",
        "写了下期的提纲，五个问题",
    ),
    "LLM 推理前沿": (
        "读 PagedAttention，做了一张卡片",
        "读 DistServe，把 prefill/decode 分离的账算了一遍",
        "看 FlashAttention-2 的实现，理解了 tiling",
        "整理一页笔记：continuous batching 的三种实现",
        "读了一篇 speculative decoding 的综述",
        "读 Mooncake 的调度部分，和我们的方案对比",
        "把最近 {n} 篇论文的结论串成一条线",
        "读 Sarathi-Serve，chunked prefill 那节很受用",
    ),
    "分布式系统": (
        "重读 Raft 的 leader election",
        "看 TiKV 的调度器设计",
        "把 CAP 的几个常见误解写成笔记",
        "读了 Dynamo 的论文，向量时钟那节",
        "研究了一下 etcd 的 lease 机制",
    ),
    "数学与概率": (
        "做了 {n} 道概率题",
        "复习信息论里的 KL 散度",
        "推了一遍 attention 的计算复杂度",
        "把矩阵分解的几何意义重新想了一遍",
    ),
    "Rust": (
        "写了 {n} 行 Rust，把 tokio 的 task 模型搞明白了",
        "用 Rust 重写一个小工具，性能提升 {pct}%",
        "读《Rust 程序设计语言》第 {n} 章",
        "和 borrow checker 搏斗了一小时，最后用 Arc 解决",
        "给 CLI 工具加了进度条和彩色输出",
    ),
    "数据库内核": (
        "读 B+ 树并发控制那一章",
        "跑了一遍 LSM tree 的写放大实验",
        "看了一遍 WAL 的恢复流程",
    ),
    "下肢力量": (
        "深蹲 {kg}kg × {reps} × {sets}",
        "硬拉 {kg}kg × {reps}，最后一组有点勉强",
        "腿举 + 保加利亚分腿蹲",
        "练完拉伸 {min} 分钟",
        "深蹲加到了 {kg}kg，动作还算干净",
    ),
    "上肢与核心": (
        "卧推 {kg}kg × {reps} × {sets}",
        "引体向上 {reps} 个 × {sets} 组",
        "肩推 + 划船，重量稳住了",
        "核心训练 {min} 分钟",
        "加了一组农夫行走",
    ),
    "晨跑": (
        "晨跑 {km} km，配速 {pace}",
        "Easy run {km} km，平均心率 {hr}",
        "间歇跑 8×400m，最后一组还能顶住",
        "沿着海湾跑了 {km} km，雾很大",
        "长距离 {km} km，最后一公里加速",
        "恢复跑 {km} km，腿还是有点沉",
        "跑完在便利店买了瓶冰水，站了十分钟",
    ),
    "半马备赛": (
        "按计划跑 {km} km，配速 {pace}",
        "跑了 {km} km 的马拉松配速",
        "赛前减量，只跑了 {km} km",
        "半马完赛，{time}",
        "把比赛日的补给和路线又过了一遍",
    ),
    "睡眠": (
        "睡了 {hrs} 小时，深度睡眠 {pct}%",
        "把入睡时间提前到 23:30",
        "睡前不刷手机，明显好睡",
        "补了一觉，状态回来了",
        "连着两天睡不够，下午效率很低",
    ),
    "冥想与呼吸": (
        "冥想 {min} 分钟",
        "4-7-8 呼吸，睡前两组",
        "走路冥想 {min} 分钟",
        "开会前做了三分钟呼吸，心率降下来了",
    ),
    "父母": (
        "和爸妈视频 {min} 分钟",
        "给家里订了体检",
        "寄了保健品回去",
        "听我妈讲了半小时邻居的事",
    ),
    "伴侣": (
        "一起做饭，聊了她最近的项目",
        "周末去看展",
        "散步 {min} 分钟，聊了明年的计划",
        "帮她改了一版简历",
        "一起把阳台收拾了出来",
    ),
    "湾区朋友": (
        "和 Kevin 吃饭，聊了他创业的事",
        "周末爬山，来了 {n} 个人",
        "帮朋友看了一版 BP",
        "老同事来湾区出差，约了顿饭",
    ),
    "行业交流": (
        "参加了一场 infra meetup",
        "和隔壁组的 tech lead 喝了咖啡",
        "在 Slack 社区回了几个问题",
        "和两个做推理的团队聊了聊",
    ),
    "储蓄率复盘": (
        "记了这个月账单，储蓄率 {pct}%",
        "砍掉两个不用的订阅",
        "把大额支出单独列了出来",
    ),
    "股权与 vesting": (
        "确认了这季度的 vesting",
        "算了一遍四年后的税",
        "把行权时间表存进日历",
    ),
    "指数定投": (
        "定投 {usd} 美元，照旧",
        "跌了，按计划加了一点",
        "把定投改成自动扣款",
    ),
    "组合再平衡": (
        "季度再平衡，调了 {pct}% 到债券",
        "看了一遍资产配置",
        "把现金仓位从 {pct}% 降下来",
    ),
    "MVP 开发": (
        "写了 {n} 个接口，跑通导入",
        "把编辑器的手感调了一遍",
        "做了 {n} 个原型，只留一个",
        "修了一个同步的竞态",
        "内测版发给了 {n} 个朋友",
        "把冷启动从 {ms}ms 降到 {ms2}ms",
        "重写存储层，为之后的协作留口子",
    ),
    "用户访谈": (
        "访谈了 {n} 位研究者，记了 {pages} 页笔记",
        "整理访谈，提炼出三个痛点",
        "给一位用户演示，看他卡在哪",
        "回访了上个月的访谈对象",
    ),
    "Newsletter": (
        "写了第 {n} 期，聊工具与注意力",
        "排版调了一遍，阅读体验好很多",
        "订阅数破了 {n}00",
        "收到一封长回信，认真回了",
    ),
    "日本行": (
        "在京都走了一天，看了三个庭院",
        "订了行程和民宿",
        "在东京见了老朋友",
        "在新干线上把这一年的计划写了一遍",
    ),
    "湾区徒步": (
        "去了 Muir Woods，走了 {km} km",
        "周六早起去海边徒步",
        "试了一条新路线，爬升 {n}00 米",
        "带了相机，拍了一路的光",
    ),
    "公寓布置": (
        "把书桌换成升降桌",
        "装了一组书架",
        "扔了两箱不用的东西",
        "给工作角加了一盏灯",
    ),
}

GENERIC_NOTES = (
    "推进了一小步，把想到的记下来",
    "花 {min} 分钟处理完这件事",
    "整理了一下思路，下次接着做",
)

HOURS = {
    "调度器重构": (9, 20), "KV Cache 与显存": (10, 20), "延迟压测与 SLO": (10, 21),
    "vLLM 集成": (10, 19), "多机部署": (11, 20),
    "招聘与面试": (10, 18), "一对一与团队成长": (9, 18), "季度规划": (9, 18),
    "博客长文": (21, 23), "内部技术文档": (14, 19), "旧博客迁移": (20, 23),
    "会议演讲": (10, 18), "开源项目": (21, 23), "播客录制": (20, 23),
    "LLM 推理前沿": (21, 23), "分布式系统": (21, 23), "数学与概率": (20, 23),
    "Rust": (20, 23), "数据库内核": (21, 23),
    "下肢力量": (7, 9), "上肢与核心": (18, 20), "晨跑": (6, 8), "半马备赛": (6, 8),
    "睡眠": (22, 23), "冥想与呼吸": (22, 23),
    "父母": (19, 21), "伴侣": (19, 22), "湾区朋友": (11, 21), "行业交流": (17, 21),
    "储蓄率复盘": (21, 23), "股权与 vesting": (21, 23), "指数定投": (9, 12),
    "组合再平衡": (21, 23),
    "MVP 开发": (21, 23), "用户访谈": (10, 18), "Newsletter": (21, 23),
    "日本行": (9, 21), "湾区徒步": (7, 12), "公寓布置": (10, 18),
}


class Ctx(dict):
    """给备注模板填数字用：同一个键在一次生成里保持一致。"""

    def __init__(self, rng: random.Random) -> None:
        super().__init__()
        self.rng = rng
        self.extra: dict[str, str] = {}

    def __missing__(self, key: str) -> str:  # noqa: D105
        value = self.extra.get(key) or self._make(key)
        self[key] = value
        return value

    def _make(self, key: str) -> str:
        rng = self.rng
        if key == "pct":
            return str(rng.choice([8, 11, 12, 15, 18, 22, 27, 31, 35, 42]))
        if key == "pct2":
            return str(rng.randint(1, 4))
        if key == "ms":
            return str(rng.choice([180, 210, 240, 265, 290, 320, 350, 380, 410, 460]))
        if key == "ms2":
            return str(rng.randint(90, 180))
        if key == "n":
            return str(rng.randint(2, 12))
        if key == "kg":
            return str(rng.choice([60, 70, 75, 80, 85, 90, 95, 100, 105, 110]))
        if key == "reps":
            return str(rng.choice([5, 6, 8, 10, 12]))
        if key == "sets":
            return str(rng.choice([3, 4, 5]))
        if key == "km":
            return f"{rng.uniform(5.0, 18.0):.1f}"
        if key == "pace":
            return f"{rng.randint(4, 5)}'{rng.randint(0, 59):02d}\""
        if key == "hr":
            return str(rng.randint(134, 166))
        if key == "min":
            return str(rng.choice([15, 20, 25, 30, 40, 45, 60, 75, 90]))
        if key == "words":
            return str(rng.choice([800, 1200, 1500, 1800, 2200, 2600]))
        if key == "hrs":
            return f"{rng.uniform(6.0, 8.4):.1f}"
        if key == "pages":
            return str(rng.choice([3, 4, 6, 8, 12]))
        if key == "usd":
            return str(rng.choice([1500, 2000, 2500, 3000, 4000]))
        if key == "time":
            return f"{rng.randint(1, 1)}:{rng.randint(30, 59):02d}:{rng.randint(0, 59):02d}"
        if key == "title":
            return rng.choice(
                ["推理调度里的三个取舍", "把 P99 当成产品指标", "为什么我们放弃了静态 batching",
                 "一个人维护 infra 的三年", "长上下文到底贵在哪"]
            )
        if key == "conf":
            return rng.choice(["Ray Summit", "QCon", "MLSys 的线下 meetup", "湾区 Infra Night"])
        if key == "name":
            return rng.choice(["Kevin", "Wei", "Anand", "小林", "Daniel"])
        return str(rng.randint(2, 9))


def make_note(thread_key: str, rng: random.Random) -> str:
    pool = NOTE_BANK.get(thread_key) or GENERIC_NOTES
    return rng.choice(pool).format_map(Ctx(rng))


# ------------------------------------------------------------------ 日历
TRAVEL = (("2025-12-21", "2026-01-02"), ("2026-04-10", "2026-04-16"))
CRUNCH = (("2026-03-01", "2026-03-13"),)
CONFERENCE = (("2026-05-18", "2026-05-22"),)
SICK = (("2026-02-03", "2026-02-06"),)
RACE_WEEK = (("2025-11-10", "2025-11-16"),)


def in_ranges(day: date, ranges) -> bool:
    return any(d(start) <= day <= d(end) for start, end in ranges)


def day_target(day: date, rng: random.Random) -> int:
    if in_ranges(day, TRAVEL):
        return rng.choice([0, 0, 1, 1])
    if in_ranges(day, CRUNCH):
        return rng.randint(7, 10)
    if in_ranges(day, CONFERENCE):
        return rng.randint(2, 3)
    if in_ranges(day, SICK):
        return rng.choice([0, 0, 1])
    if in_ranges(day, RACE_WEEK):
        return rng.randint(2, 4)
    base = (4, 5, 5, 4, 3, 2, 1)[day.weekday()]
    count = max(0, base + rng.choice([-1, 0, 0, 1]))
    if rng.random() < 0.06:
        return 0
    return count


# ------------------------------------------------------------------ 时间线事件
TIMELINE = (
    ("2025-09-14", "rename", "个人博客", "博客长文"),
    ("2025-10-05", "move", "英语表达", "工程手艺"),
    ("2025-11-16", "status", "半马备赛", Status.DONE.value),
    ("2025-12-01", "status", "半马备赛", Status.ARCHIVED.value),
    ("2026-02-08", "rename", "Side Project", "独立产品 Memex"),
    ("2026-06-12", "status", "播客", Status.PAUSED.value),
)


def apply_timeline(service: LifeManagerService, node_ids: dict[str, str], day: date) -> None:
    for when, action, target, payload in TIMELINE:
        if d(when) != day:
            continue
        node_id = node_ids.get(target)
        if node_id is None:
            continue
        if action == "rename":
            service.rename_node(node_id, payload)
        elif action == "move":
            service.move_node(node_id, node_ids[payload])
        elif action == "status":
            service.set_status(node_id, Status(payload))
        backdate_last_event(service, node_id, f"{when} 21:40:00")


def backdate_last_event(service: LifeManagerService, node_id: str, stamp: str) -> None:
    with service.db.transaction() as tx:
        row = tx.execute(
            "SELECT id FROM events WHERE node_id = ? ORDER BY rowid DESC LIMIT 1", (node_id,)
        ).fetchone()
        if row is not None:
            tx.execute("UPDATE events SET created_at = ? WHERE id = ?", (stamp, row["id"]))


# ------------------------------------------------------------------ 构建
def build_tree(service: LifeManagerService) -> dict[str, str]:
    ids: dict[str, str] = {}
    for area in TREE:
        area_node = service.create_node(NodeType.AREA, area["name"], None)
        ids[area["name"]] = area_node.id
        for process in area["processes"]:
            process_node = service.create_node(
                NodeType.PROCESS, process.get("initial", process["name"]), area_node.id
            )
            ids[process["name"]] = process_node.id
            if process.get("initial"):
                ids[process["initial"]] = process_node.id
            for thread in process["threads"]:
                thread_node = service.create_node(
                    NodeType.THREAD, thread.get("initial", thread["name"]), process_node.id
                )
                ids[thread["name"]] = thread_node.id
                if thread.get("initial"):
                    ids[thread["initial"]] = thread_node.id
    return ids


def backdate_nodes(service: LifeManagerService, ids: dict[str, str]) -> None:
    """把节点的创建时间铺回过去。

    规则：先建领域、再建进程、最后建线程，且节点的创建时间必须早于它自己
    （以及子节点）的第一条活动记录 —— 否则「变化历史」里会出现
    「2025-10-02 创建，但 7 月就有记录」这种一眼假的时间线。
    """
    rng = random.Random(20260701)
    first_activity: dict[str, date] = {
        row["node_id"]: date.fromisoformat(row["first"])
        for row in service.db.conn.execute(
            "SELECT node_id, MIN(activity_date) AS first FROM activities GROUP BY node_id"
        )
    }

    def first_of(node_id: str) -> date | None:
        found = first_activity.get(node_id)
        children = service.children(node_id, include_deleted=True)
        for child in children:
            child_first = first_of(child.id)
            if child_first and (found is None or child_first < found):
                found = child_first
        return found

    updates: list[tuple[str, str, str]] = []
    for node_id in dict.fromkeys(ids.values()):
        node = service.require_node(node_id)
        first = first_of(node_id)
        if first is None:
            first = START + timedelta(days=60)
        if node.type is NodeType.AREA:
            created_day = max(START, first - timedelta(days=rng.randint(2, 6)))
        elif node.type is NodeType.PROCESS:
            created_day = max(START, first - timedelta(days=rng.randint(3, 15)))
        else:
            created_day = max(START, first - timedelta(days=rng.randint(5, 40)))
        created = datetime.combine(created_day, datetime.min.time()).replace(
            hour=rng.randint(9, 22), minute=rng.randint(0, 59)
        )
        stamp = created.strftime("%Y-%m-%d %H:%M:%S")
        updates.append((stamp, stamp, node_id))
    with service.db.transaction() as tx:
        tx.executemany("UPDATE nodes SET created_at = ?, updated_at = ? WHERE id = ?", updates)
        for stamp, _same, node_id in updates:
            tx.execute(
                "UPDATE events SET created_at = ? WHERE node_id = ? AND event_type = 'create'",
                (stamp, node_id),
            )


def fill_text_fields(service: LifeManagerService, ids: dict[str, str]) -> None:
    rng = random.Random(77)
    for area in TREE:
        for process in area["processes"]:
            process_id = ids[process["name"]]
            if process.get("desc"):
                service.set_description(process_id, process["desc"])
                created = datetime.strptime(
                    service.require_node(process_id).created_at, "%Y-%m-%d %H:%M:%S"
                )
                when = created + timedelta(days=rng.randint(20, 90))
                if when.date() >= END:
                    when = datetime.combine(END - timedelta(days=rng.randint(5, 30)), datetime.min.time())
                when = when.replace(hour=rng.randint(20, 22), minute=rng.randint(0, 59))
                backdate_last_event(
                    service, process_id, when.strftime("%Y-%m-%d %H:%M:%S")
                )
            if process.get("next"):
                service.set_next_action(process_id, process["next"])
                backdate_last_event(
                    service, process_id, f"{END - timedelta(days=rng.randint(1, 9))} 22:05:00"
                )
            for thread in process["threads"]:
                if not thread.get("next"):
                    continue
                thread_id = ids[thread["name"]]
                service.set_next_action(thread_id, thread["next"])
                created = datetime.strptime(
                    service.require_node(thread_id).created_at, "%Y-%m-%d %H:%M:%S"
                )
                when = max(created + timedelta(days=1), datetime.combine(
                    END - timedelta(days=rng.randint(1, 20)), datetime.min.time()
                ))
                when = when.replace(hour=rng.randint(21, 23), minute=rng.randint(0, 59))
                backdate_last_event(
                    service, thread_id, when.strftime("%Y-%m-%d %H:%M:%S")
                )


def thread_weights() -> dict[str, float]:
    weights: dict[str, float] = {}
    for area in TREE:
        for process in area["processes"]:
            for thread in process["threads"]:
                weights[thread["name"]] = float(thread.get("weight", 1))
    return weights


def active_threads(day: date) -> list[str]:
    names: list[str] = []
    for area in TREE:
        for process in area["processes"]:
            for thread in process["threads"]:
                window = thread.get("window")
                if window:
                    start, end = window
                    if day < d(start) or (end and day > d(end)):
                        continue
                names.append(thread["name"])
    return names


def seed_activities(service: LifeManagerService, ids: dict[str, str]) -> dict[str, int]:
    rng = random.Random(424242)
    weights = thread_weights()
    per_day: dict[str, int] = {}
    backdates: list[tuple[str, str]] = []

    day = ACTIVITY_START
    while day <= END:
        apply_timeline(service, ids, day)
        target = day_target(day, rng)
        allowed = active_threads(day)
        allowed = [name for name in allowed if weights.get(name, 0) > 0]
        if not allowed:
            day += timedelta(days=1)
            continue
        pool = [name for name in allowed for _ in range(max(1, int(weights[name] * 10)))]

        picks = rng.choices(pool, k=target) if target else []
        rows = []
        for name in picks:
            low, high = HOURS.get(name, (9, 20))
            hour = rng.randint(low, high)
            minute = rng.randint(0, 59)
            second = rng.randint(0, 59)
            rows.append((hour, minute, second, name, make_note(name, rng)))
        rows.sort()
        for hour, minute, second, name, note in rows:
            activity = service.record_activity(ids[name], note, day.isoformat())
            stamp = f"{day.isoformat()} {hour:02d}:{minute:02d}:{second:02d}"
            backdates.append((stamp, activity.id))
        per_day[day.isoformat()] = len(rows)
        day += timedelta(days=1)

    # 今天凌晨记两条，让「今天」不是空的
    for name, note, hh, mm in (
        ("调度器重构", "凌晨把灰度结果看完了，P99 稳在 268ms", 1, 12),
        ("晨跑", "夜跑 6.4 km，配速 5'31\"", 0, 41),
    ):
        activity = service.record_activity(ids[name], note, TODAY.isoformat())
        backdates.append((f"{TODAY.isoformat()} {hh:02d}:{mm:02d}:17", activity.id))
    per_day[TODAY.isoformat()] = 2

    with service.db.transaction() as tx:
        tx.executemany("UPDATE activities SET created_at = ? WHERE id = ?", backdates)
    return per_day


def seed_associations(service: LifeManagerService, ids: dict[str, str]) -> None:
    pairs = (
        ("开源项目", "独立产品 Memex", "2026-02-14"),
        ("博客长文", "独立产品 Memex", "2026-03-02"),
        ("用户访谈", "演讲与社区", "2026-04-20"),
        ("英语表达", "技术领导", "2025-10-06"),
    )
    for thread, process, when in pairs:
        service.associate(ids[thread], ids[process])
        backdate_last_event(service, ids[thread], f"{when} 21:10:00")


def seed_pins(service: LifeManagerService, ids: dict[str, str]) -> None:
    for name, when in (
        ("推理调度器", "2026-07-06"),
        ("MVP 开发", "2026-08-17"),
        ("晨跑", "2026-09-01"),
    ):
        service.set_pinned(ids[name], True)
        backdate_last_event(service, ids[name], f"{when} 08:20:00")


def seed_slogans(service: LifeManagerService, ids: dict[str, str]) -> None:
    slogans = (
        ("2025-07-01", "把注意力放在能复利的事情上。"),
        ("2025-10-20", "先做最难的 90 分钟。"),
        ("2026-01-05", "记录不是为了证明努力，是为了看见方向。"),
        ("2026-05-11", "慢一点没关系，别停。"),
        ("2026-09-14", "每天推进 1%，一年就是 37 倍。"),
    )
    for when, text in slogans:
        service.set_slogan(text)
        with service.db.transaction() as tx:
            row = tx.execute("SELECT id FROM slogans ORDER BY rowid DESC LIMIT 1").fetchone()
            if row is not None:
                tx.execute(
                    "UPDATE slogans SET created_at = ? WHERE id = ?",
                    (f"{when} 09:00:00", row["id"]),
                )


def delete_demo_thread(service: LifeManagerService, ids: dict[str, str]) -> None:
    node_id = ids["旧博客迁移"]
    service.delete_node(node_id)
    with service.db.transaction() as tx:
        tx.execute("UPDATE nodes SET deleted_at = ? WHERE id = ?", ("2025-08-26 22:40:00", node_id))
        row = tx.execute(
            "SELECT id FROM events WHERE node_id = ? AND event_type = 'delete'"
            " ORDER BY rowid DESC LIMIT 1",
            (node_id,),
        ).fetchone()
        if row is not None:
            tx.execute(
                "UPDATE events SET created_at = ? WHERE id = ?",
                ("2025-08-26 22:40:00", row["id"]),
            )


# ------------------------------------------------------------------ 日记
ANCHORS = {
    "2025-07-01": "从今天起把生活摊开来看。工作、训练、读书、写东西，都各开一条线，省得脑子里老挂着。",
    "2025-08-12": "第一次觉得调度器这个东西可以讲清楚了。给组里讲了一遍，大家问的问题比我预想的深。",
    "2025-09-14": "把博客从旧站搬过来，顺手改了个名字。以前叫「个人博客」，听着像个闲置的角落。",
    "2025-11-16": "半马完赛，1:38:47。最后三公里腿已经不是自己的了，但没停下来。这个项目可以归档了。",
    "2025-12-24": "在京都。早上六点起来走了一圈，街上几乎没人。这一年跑得太急了，今天才觉得慢下来。",
    "2026-01-12": "Side Project 正式立项。给自己定了一个很克制的目标：先服务好 50 个研究者。",
    "2026-02-08": "产品有了名字：Memex。改完名的那一下，感觉它真的存在了。",
    "2026-03-05": "调度器新版本全量上线。P99 从 410ms 掉到 268ms，盯着看板上那条线看了很久。",
    "2026-03-14": "一次小故障复盘。问题不大，但暴露了我们没有把失败路径画出来。补文档。",
    "2026-04-02": "绩效沟通。老板说了一句「你现在更像是把这个团队当成自己的在带」。这句话比评级有用。",
    "2026-05-20": "在大会上讲完。Q&A 被问到一个没准备的问题，现场推了一遍，反而成了全场最好的部分。",
    "2026-06-12": "播客先停一停。不是不喜欢，是同一段时间里只能做好三件事，它排在第四。",
    "2026-07-08": "Memex 内测版发出去 12 份。晚上收到第一条很长的反馈，认真回了。",
    "2026-09-21": "订阅数破千。没什么仪式感，只是把这条线的优先级又往上提了一格。",
    "2026-10-10": "季度复盘。今年到现在，最值得的不是做完了什么，是终于知道自己不该做什么。",
}

DIARY_TEMPLATES = (
    "今天大部分时间在「{top}」上，推进了两步。晚上还是出去跑了 {km} km，算是把脑子清空。",
    "「{top}」卡了一下午，最后发现问题在一个很小的假设上。记下来，别再犯。",
    "一天开了三个会，只有「{top}」那一段是真正在做事的。明天把它放到上午。",
    "状态一般。只做了「{top}」这件事，剩下的时间用来读东西和发呆。也算数。",
    "今天效率很高，{n} 件事都收尾了。晚上早点睡，别把好状态用光。",
    "有点累。把「{top}」往前挪了一点点，然后就收工了。",
    "和「{top}」有关的一个想法，洗澡的时候想通了，赶紧记下来。",
    "今天没做出什么看得见的成果，但在「{top}」上把方向想清楚了。",
    "跑完步回来接着做「{top}」，思路比早上清楚多了。",
    "「{top}」推进得比预期慢。提醒自己：慢不是问题，停才是。",
    "把手机放到另一个房间，两个小时的深度工作，抵得上一整天。",
    "今天见了几个人，聊的都是「{top}」。有时候说出来才知道自己怎么想。",
)


def seed_diary(service: LifeManagerService, per_day: dict[str, int]) -> int:
    rng = random.Random(9090)
    index: dict[str, dict[str, int]] = {}
    for row in service.db.conn.execute(
        "SELECT activity_date, node_id, COUNT(*) AS n FROM activities GROUP BY activity_date, node_id"
    ):
        index.setdefault(row["activity_date"], {})[row["node_id"]] = int(row["n"])

    names = {node.id: node.name for node in service.all_nodes()}
    written = 0
    for day_text, counts in sorted(index.items()):
        if day_text in ANCHORS:
            body = ANCHORS[day_text]
        else:
            total = per_day.get(day_text, 0)
            if total < 3 or rng.random() > 0.52:
                continue
            top_id = max(counts, key=lambda key: counts[key])
            top = names.get(top_id, "手头的事")
            template = rng.choice(DIARY_TEMPLATES)
            body = template.format(
                top=top, n=total, km=f"{rng.uniform(5.0, 12.0):.1f}"
            )
        diary.write_day(day_text, body)
        written += 1
    for day_text, body in ANCHORS.items():
        if day_text not in index:
            diary.write_day(day_text, body)
            written += 1
    # 今天：和凌晨那两条记录对得上，打开日记页不是空白的
    today_text = TODAY.isoformat()
    if not diary.read_day(today_text).strip():
        diary.write_day(
            today_text,
            "凌晨把灰度结果看完了，P99 稳在 268ms。明天推全量，然后好好睡一觉。",
        )
        written += 1
    return written


# ------------------------------------------------------------------ 主流程
def main() -> int:
    parser = argparse.ArgumentParser(description="生成演示数据")
    parser.add_argument("--force", action="store_true", help="清空现有数据库后重建")
    args = parser.parse_args()

    database_path = paths.DATABASE_PATH
    if database_path.exists():
        probe = Database(database_path)
        probe.initialize(seed=False)
        existing = probe.node_count()
        probe.close()
        if existing and not args.force:
            print(f"数据库里已经有 {existing} 个节点，加 --force 才会清空重建。")
            return 1
        if args.force:
            for suffix in ("", "-wal", "-shm"):
                target = Path(str(database_path) + suffix)
                if target.exists():
                    target.unlink()

    db = Database(database_path)
    db.initialize(seed=False)
    db.set_meta("seeded", "1")
    service = LifeManagerService(db)

    print("① 建树…")
    ids = build_tree(service)
    print("② 逐日记录活动…")
    per_day = seed_activities(service, ids)
    print("③ 回填节点的创建时间…")
    backdate_nodes(service, ids)
    print("④ 写注释与下一步行动…")
    fill_text_fields(service, ids)
    print("⑤ 关联 / 置顶 / 标语…")
    seed_associations(service, ids)
    seed_pins(service, ids)
    seed_slogans(service, ids)
    delete_demo_thread(service, ids)
    print("⑥ 写日记…")
    # 日记先清空，避免和上一次运行叠加
    if paths.DIARY_PATH.exists():
        paths.DIARY_PATH.unlink()
    diary.ensure_file()
    written = seed_diary(service, per_day)

    counts = service.stats()
    total_nodes = (
        counts.get("areas", 0) + counts.get("processes", 0) + counts.get("threads", 0)
        + counts.get("deleted_nodes", 0)
    )
    active_days = db.conn.execute(
        "SELECT COUNT(DISTINCT activity_date) AS n FROM activities"
    ).fetchone()["n"]
    print("\n完成：")
    print(f"  节点 {total_nodes}，活动 {counts.get('activities')}，"
          f"历史事件 {counts.get('events')}，进行中关联 {counts.get('active_associations')}")
    print(f"  有记录的天数 {active_days}，日记 {written} 天")
    db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
