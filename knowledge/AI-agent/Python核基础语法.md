# Python 核心语法 · 精华笔记

> 整理自《第2章 Python核心语法》01–06 节课件（共 6 份 PPT、312 页）
> 定位：去掉重复页/过渡页/练习题，只保留**概念定义、语法模板、方法速查表、易错点**。
> 适用：快速复习 + 编码速查。

---

## 知识地图

| 小节 | 主题 | 一句话概括 |
|---|---|---|
| 01 | 数据存储与运算 | 数据怎么写（字面量）、怎么存（变量）、什么类型、怎么进出、怎么运算 |
| 02 | 流程控制语句 | 顺序 → 分支（if / match）→ 循环（while / for / 嵌套） |
| 03 | 数据存储容器 | list / str / tuple / set / dict，一个装多个数据的五种方式 |
| 04 | 函数 | 把代码打包复用：参数、返回值、作用域、不定长参数、lambda、类型注解 |
| 05 | 模块与包 | 把函数打包复用：`.py` 文件 = 模块，带 `__init__.py` 的文件夹 = 包 |
| 06 | 面向对象基础 | 把数据和功能打包：类 / 对象 / 属性 / 方法 / 魔法方法 / 异常 |

---

# 01 数据存储与运算

## 1.1 字面量（怎么写数据）

**字面量**：程序中直接书写的固定值。

| 类型 | 说明 | 示例 |
|---|---|---|
| `int` 整数 | 不带小数 | `10` `18` `-5` `0` |
| `float` 浮点数 | 带小数 | `8.5` `3.14` `1.0` `-3.5` |
| `bool` 布尔 | 真 / 假，**本质是数字**，运算时 True→1、False→0 | `True` `False` |
| `str` 字符串 | 引号引起来的文本 | `"人生苦短，我用Python"` |
| `NoneType` 空值 | 只有一个值，表示"无" | `None` |
| 数据容器 | 存多项数据 | 列表 / 元组 / 集合 / 字典 |

⚠️ 易错：`10010` 是数字，`"10010"` 是字符串；`True` 是布尔，`"True"` 是字符串。

## 1.2 变量（怎么存数据）

**变量**：程序中用来存储**单个**数据的容器。

```python
num = 1114.1        # 变量名 = 变量的值（赋值：把右边给左边）
a, b = 1, "Python"  # 一条语句定义多个变量
```

- 变量是**容器（空间）**，不是里面的数据；一个变量只能存一个值
- 变量**必须先赋值才能使用**
- Python 是**动态类型**语言：变量本身没有类型，类型是它存的数据的类型；同一变量可以先后接收不同类型的值

## 1.3 标识符命名

**命名规则（硬性）**
1. 只能含 字母 `a-zA-Z`、数字 `0-9`、下划线 `_`
2. **不能以数字开头**
3. 不能使用关键字（`if` `else` `elif` `for` `while` `and` `or` `not` `True` `False` `None` …）
4. 严格区分大小写：`age` / `Age` / `AGE` 是三个不同变量

**命名规范（约定，遵循 PEP8）**
- 见名知意、英文字母全小写、多单词用下划线连接 → **蛇形命名法**（`update_time`、`user_first_name`）

> 合法：`name` `_name` `__name` `Name` `na_me` `name_`
> 非法：`6name`（数字开头）、`na$me`（非法字符）、`and`（关键字）

## 1.4 常见数据类型与查看

| 标准名 | 描述 |
|---|---|
| `int` / `float` / `str` / `bool` / `NoneType` | 整数 / 小数 / 字符串 / 布尔 / 空值 |

```python
print(type("Hello"))            # <class 'str'>   查看实际类型
print(type(num))                # 变量无类型，返回的是其存储数据的类型
print(isinstance(num, int))     # False           是否属于指定类型，返回 bool
```

## 1.5 字符串

```python
s1 = "Hello"        # 双引号
s2 = 'Python'       # 单引号（与双引号等效）
s3 = """多行
字符串"""            # 三引号
```

| 转义字符 | 作用 |
|---|---|
| `\'` `\"` | 表示单/双引号 |
| `\n` | 换行 |
| `\t` | 制表符缩进 |

**拼接与格式化**

```python
# ① + 拼接：只能拼字符串，其他类型必须先 str(..)
message = "大家好，我是" + name + "，今年" + str(age) + "岁"

# ② % 占位符：占位符个数与后面变量个数必须一致
print("吉多·范罗苏姆: %s , %s" % (s1, s2))

# ③ f-string（推荐）
print(f"大家好, 我是 {name}, 今年 {age} 岁")
```

> `+` 拼接的三个痛点：写法繁琐、要手动类型转换、破坏字符串完整性 → **优先用 f-string**。

## 1.6 输入与输出

```python
name = input("请输入您的姓名：")   # 获取键盘输入
print(f"欢迎您, {name}")           # 输出到控制台
```

⚠️ **无论输入什么，`input()` 返回的永远是字符串**。需要计算时先转换：

```python
int(..) / float(..) / str(..) / bool(..)
```

## 1.7 运算符

**算术运算符**

| 运算符 | 描述 | 示例 |
|---|---|---|
| `+` `-` `*` | 加减乘 | `3 * 8` |
| `/` | 除法，**结果是小数** | `10 / 5` → `2.0` |
| `//` | 整除，结果为整数 | `10 // 3` → `3` |
| `%` | 取余/求模 | `10 % 3` → `1` |
| `**` | 幂运算 | `10 ** 3` → `1000` |

⚠️ 浮点运算可能**损失精度**（计算机底层二进制无法精确表示所有小数）。

**赋值运算符**：`=` `+=` `-=` `*=` `/=` `%=` `//=` `**=`（`num += 2` ≡ `num = num + 2`）

**比较运算符**：`==` `!=` `>` `>=` `<` `<=` → 返回布尔值

**逻辑运算符**

| 运算符 | 描述 |
|---|---|
| `and` | 并且：左右都为 True 才 True |
| `or` | 或者：有一个为 True 就 True |
| `not` | 非：取反 |

```python
num % 2 == 0              # 判断偶数
10 <= x <= 20             # 判断是否在区间内（Python 支持链式比较）
```

---

# 02 流程控制语句

## 2.1 条件判断

```python
# ① 基本 if
if 条件:
    条件成立时执行的操作        # 缩进 4 个空格表示归属

# ② if...else
if 条件:
    操作1
else:
    操作2                      # else 不写条件

# ③ if...elif...else（多分支）
if 条件1:
    操作1
elif 条件2:                    # elif 可以写多个
    操作2
else:                          # else 可有可无，有则必须在最后
    操作3
```

注意事项：
- 判断结果必须是**布尔类型**
- 条件后**别忘冒号 `:`**
- 通过**缩进**（建议 4 空格）描述层级
- 多分支**从上到下判断，命中前面的就不再判断后面的**（所以范围判断要注意顺序）

```python
# 折扣计算（注意顺序：从大到小）
if amount >= 500:   rate = 0.8
elif amount >= 300: rate = 0.9
elif amount >= 100: rate = 0.95
else:               rate = 1.0
```

## 2.2 模式匹配 match...case（Python 3.10+）

```python
match day:
    case "1":  print("周一：工作会议日")
    case "2":  print("周二：学习培训日")
    case "6" | "7": print("周末：休息放松")   # | 表示"或"
    case _:    print("输入错误")              # _ 匹配其他所有情况
```

- 执行流程：先算 `match` 后的表达式值 → 从上到下依次匹配 `case` → 都不匹配则走 `case _`
- **选型建议**：基于某个变量的**多个固定值**分支 → 用 `match`；涉及**复杂逻辑、范围比较、组合条件** → 用 `if`

## 2.3 while 循环

```python
while 条件表达式:
    循环体语句
else:                       # 可选
    循环"正常"结束时执行     # 被 break 中断则不执行
```

- 条件必须是布尔类型；**必须规划好终止条件**，否则死循环
- 适用：循环**次数未知**，只知道开始/结束的条件

## 2.4 for 循环

```python
for 元素 in 待处理数据集:      # 本质：轮询遍历机制
    循环体代码
else:                          # 可选
    循环结束时执行
```

- 适用：对**已知数据集**遍历，或**已知次数**的循环

**range 语句**——生成数字序列

| 用法 | 含义 | 示例 |
|---|---|---|
| `range(end)` | 0 到 end-1 | `range(5)` → 0,1,2,3,4 |
| `range(start, end)` | start 到 end-1 | `range(2,8)` → 2…7 |
| `range(start, end, step)` | 带步长 | `range(0,10,2)` → 0,2,4,6,8 |

> **不含结束值本身**（左闭右开）。

## 2.5 嵌套循环与跳转

```python
for i in 待处理数据集1:        # 外层循环（控制行）
    for j in 待处理数据集2:    # 内层循环（控制列）
        ...
```

| 关键字 | 作用 |
|---|---|
| `break` | 只能用在循环中，**结束/跳出**整个循环 |
| `continue` | 只能用在循环中，**中断本次**，直接进入下一次 |

经典练习：99 乘法表、等腰直角三角形、数字金字塔、国际象棋棋盘、猜数字游戏、5 次登录机会。

---

# 03 数据存储容器

## 3.1 五类容器对比（核心表）

| 特性 | 字符串 str | 列表 list | 元组 tuple | 集合 set | 字典 dict |
|---|---|---|---|---|---|
| 有序性 | 有序 | 有序 | 有序 | **无序** | 有序（3.7+） |
| 重复元素 | 允许 | 允许 | 允许 | **不允许** | key 不允许 |
| 可变性 | **不可变** | 可变 | **不可变** | 可变 | 可变 |
| 索引访问 | 支持 | 支持 | 支持 | **不支持** | 不支持 |
| 切片 | 支持 | 支持 | 支持 | **不支持** | 不支持 |
| 典型场景 | 文本处理 | 有序可重复集合 | 固定数据记录 | 去重集合 | 键值对 |

## 3.2 序列通用：索引与切片

- **正向索引**从 `0` 开始；**反向索引**从 `-1` 开始
- 切片语法：`序列[start:end:step]`
  - `start` 缺省为 0；`end` 缺省为末尾；`step` 缺省为 1（`-1` 表示从后向前）
  - **不包含结束索引位置的元素**
  - 列表、字符串、元组都支持

```python
s = [54, 15, 75, 108, 23, 78, 75]
s[0]        # 54      s[-1]  # 75
s[0:5:1]    # 取前5个
s[0:5:2]    # 隔一个取一个
s[::-1]     # 反转（判断回文串的经典写法）
```

⚠️ 索引越界会报错。

## 3.3 列表 list

```python
列表名 = [元素1, 元素2, 元素3]      # 可存不同类型、可重复、有序、可修改
list1[0] = "A"                      # 改
del list1[3]                        # 删
```

| 方法 | 作用 |
|---|---|
| `append(x)` | 尾部追加元素 |
| `insert(i, x)` | 在指定索引**之前**插入 |
| `remove(x)` | 移除第一个匹配到的值 |
| `pop(i)` | 删除指定索引元素（不传则删最后一个），并返回该元素 |
| `sort()` | 排序（元素类型需一致） |
| `reverse()` | 反转 |

```python
# 合并两个列表
list3 = list1 + list2
list3 = [*list1, *list2]        # 解包

# 判断元素是否存在
if x in list1: ...              # 返回 bool

# 统计三件套
min(list) / max(list) / sum(list) / len(list)
```

**列表推导式**

```python
[要插入的数据 for i in 列表]                  # 格式1
[要插入的数据 for i in 列表 if 条件]          # 格式2
squares = [i**2 for i in range(1, 21)]       # 1-20 的平方
evens   = [i for i in nums if i % 2 == 0]    # 提取偶数
```

## 3.4 字符串 str

**特点**：不可变性（无法修改）、有序性、可迭代性。

| 方法 | 作用 |
|---|---|
| `find(sub)` | 查找子串，返回首次出现的索引，找不到返回 `-1` |
| `count(sub)` | 统计子串出现次数 |
| `upper()` / `lower()` | 转大写 / 小写 |
| `split(sep)` | 按分隔符切分为列表 |
| `strip()` | 去除两端空白或指定字符 |
| `replace(old, new)` | 替换子串 |
| `startswith(sub)` | 是否以指定子串开头，返回布尔 |

```python
if sub in s: ...        # 判断子串是否存在
s == s[::-1]            # 判断回文串
```

## 3.5 元组 tuple

```python
t1 = (5, 7, 9, 1)       # 定义
t2 = 5, 7, 9, 1         # 组包（括号可省略）
t3 = ()  /  tuple()     # 空元组
t4 = ('A',)             # ⚠️ 单元素元组必须加逗号
```

- 特点：可存不同类型、**可重复、有序、不可修改**（只读）；支持索引与切片
- 查询方法：`count(x)` 统计数量、`index(x)` 首次出现的索引（不存在会报错）

**组包与解包**

```python
a, b, c, d = t1                 # 基础解包
x, *y, z = t2                   # x=5, y=[7,9], z=1（* 收集剩余元素，生成列表）
a, b = b, a                     # 一行交换两个变量
a, b, c = c, a, b               # 一行完成三变量轮换
```

## 3.6 集合 set

```python
s1 = {"C", "D", "X", "T"}       # 定义
s2 = set()                      # ⚠️ 空集合只能用 set()，{} 是空字典
```

- 特点：**无序、不可重复（自动去重）、可修改**；**不支持下标索引**

| 操作 | 含义 |
|---|---|
| `add(x)` / `remove(x)` / `pop()` / `clear()` | 添加 / 删除（不存在会报错）/ 随机删并返还 / 清空 |
| `difference(s2)` | 差集（在 s1 不在 s2） |
| `union(s2)` | 并集 |
| `intersection(s2)` | 交集 |

```python
s1 & s2     # 交集
s1 | s2     # 并集
s1 - s2     # 差集
{i**2 for i in nums if 条件}    # 集合推导式
```

## 3.7 字典 dict

```python
dict1 = {"王林": 675, "李慕婉": 608}     # 键值对 key: value
dict2 = {}  /  dict()                    # 空字典
score = dict1["王林"]                    # 依 key 取 value
```

- 特点：键值对存储、**key 唯一**、可修改
- ⚠️ value 可以是**任意类型**，key 必须是**不可变类型**（不能是 list / set / dict）
- ⚠️ 字典**没有索引下标**，只能按 key 取值；key 重复定义时后面的覆盖前面的

| 操作 | 写法 |
|---|---|
| 增 / 改 | `dict[key] = value`（key 不存在则新增，存在则修改） |
| 删 | `del dict[key]`；`v = dict.pop(key)`（删并返回值） |
| 查 | `dict[key]`；`dict.get(key)` |
| 遍历 | `dict.keys()` / `dict.values()` / `dict.items()` |

**嵌套结构（实战常用）**

```python
# 列表套字典：多条记录
students = [{"name": "王林", "chinese_score": 90.0, ...}, ...]
# 字典套字典：按 key 直接索引
cart = {"Meta80": {"price": 6999, "num": 2}, "鼠标": {...}}
```

---

# 04 函数

## 4.1 定义与调用

```python
def 函数名(参数列表):
    函数体
    return 返回值          # 参数与 return 都可有可无

函数名(参数)              # 调用
```

- **先定义后调用**；定义时函数体不执行，调用时才执行
- 参数与返回值由需求决定；返回值可以是多个（**多返回值会被封装成元组**，靠解包接收）
- `return` 只负责**返回**，不负责打印；输出要配合 `print()`

## 4.2 形参 / 实参

- **形参**：定义时括号里的参数，只在函数内使用（局部变量）
- **实参**：调用时实际传入的参数

## 4.3 函数说明文档（Docstring）

```python
def circle_area_len(r):
    """
    该函数用于根据圆的半径, 计算圆的面积和圆的周长
    :param r: 圆的半径
    :return: 圆的面积 , 圆的周长
    """
    return 3.14 * r * r, 2 * 3.14 * r
```

查看方式：`help(函数名)`，或 IDE 中鼠标悬浮（推荐）。

## 4.4 嵌套调用

一个函数中调用另一个函数。调用遵循**栈结构**：LIFO（后进先出），最后被调用的函数最先返回。

## 4.5 变量作用域

| 类型 | 定义位置 | 可用范围 |
|---|---|---|
| 全局变量 | 函数外部（通常文件顶部） | 整个文件（含函数内） |
| 局部变量 | 函数内部 | 仅该函数内；函数执行完自动销毁 |

```python
num1 = 1
def fun1():
    global num1          # 声明：接下来用的是全局变量（先声明再使用）
    num1 = 100
```

> 建议：尽量用**参数和返回值**传数据，少依赖全局变量；`global` 主要用于状态、配置、计数器场景。

## 4.6 传参方式

```python
reg_stu("张三", 18, "男", "北京")                    # 位置参数：顺序必须一致
reg_stu(name="张三", age=18, gender="男", city="北京") # 关键字参数：顺序不限
reg_stu("赵四", 28, gender="男", city="上海")         # 混用：位置参数必须在前
```

| 方式 | 优点 | 缺点 | 场景 |
|---|---|---|---|
| 位置参数 | 简洁 | 可读性差、易错、难维护 | 参数少（≤3 个）且顺序自然 |
| 关键字参数 | 可读性强、易维护扩展 | 代码繁琐 | 参数多或易混淆 |

> 黄金法则：半年后回头看能否一眼看出每个参数的含义，不能就用关键字参数。

## 4.7 默认参数

```python
def reg_stu(name, age, gender, city='北京'):   # 默认值
    ...
reg_stu("张三", 18, "男")                       # 用默认值
reg_stu("赵四", 22, "男", "深圳")               # 传值则覆盖默认值
```

⚠️ **默认参数必须放在无默认值参数的后面**。

## 4.8 不定长参数

| 类型 | 写法 | 收集为 | 典型场景 |
|---|---|---|---|
| 位置传递 | `*args` | **元组** tuple | 数量不确定的数据 |
| 关键字传递 | `**kwargs` | **字典** dict | 数量不确定的选项/配置 |

```python
def calc_data(*args, **kwargs):
    min_data, max_data = min(args), max(args)
    avg_data = sum(args) / len(args)
    if kwargs.get('round'):
        avg_data = round(avg_data, kwargs.get('round'))
    return min_data, max_data, avg_data

calc_data(100, 200, 300, round=2, count=0)
```

> `args` / `kwargs` 只是约定俗成的名字，不是关键字，可换成任意合法变量名。

## 4.9 函数作为参数（高阶函数）

```python
def add(x, y): return x + y
def calc(x, y, oper): return oper(x, y)     # 传的是"封装的逻辑"

result = calc(10, 20, add)
```

## 4.10 匿名函数 lambda

```python
add = lambda x, y: x + y        # lambda 参数列表 : 表达式
out_line = lambda: print('-' * 25)
```

- 返回结果时**不需要写 return**，表达式的值即为结果
- 适合：逻辑简单（单行）、只用一次（常作高阶函数参数）
- 逻辑复杂、需复用、需文档说明 → 用命名函数
- **可读性和可维护性比简洁性更重要**

## 4.11 递归

```python
def factorial(n):               # n! = n * (n-1)!
    if n == 1:
        return 1                # 递归出口
    return n * factorial(n - 1)
```

## 4.12 列表推导式 vs 生成器表达式

| 写法 | 求值 | 内存 | 场景 |
|---|---|---|---|
| `[表达式 for i in 数据集 if 条件]` | 立即求值，一次生成整个列表 | 占用大 | 数据量小、需重复使用/多次访问 |
| `(表达式 for i in 数据集 if 条件)` | 惰性求值，按需逐个生成 | 省内存 | 大数据集、`sum()/max()/min()` 的参数 |

## 4.13 类型注解

```python
a: int = 695
names: list[str] = ["A", "C", "E"]
options: dict[str, int] = {"count": 0}
goods: tuple[str, int, int] = ("手机", 5999, 1)

def calc(scores: list[int]) -> float:
    return sum(scores) / len(scores)

def calc_data(scores: list[int]) -> tuple[int, int, float]: ...
```

- 好处：结构更清晰、逻辑更安全、IDE 补全更准确、提前发现潜在问题
- ⚠️ Python 是动态类型语言，**类型注解只是提示，不是强制约束**
- 团队协作、长期维护的项目推荐使用

---

# 05 模块与包

## 5.1 模块

**一个 `.py` 文件就是一个模块**，是 Python 程序的基本组织单位，里面可定义变量、函数、类及可执行代码。

**作用**：提高代码复用性、降低开发门槛、避免命名冲突。

```python
import random                       # 内置/第三方模块：math、os、datetime、re、random、sys、time、csv
print(random.choice(names))
```

## 5.2 导入方式速查

| 导入形式 | 示例 | 调用方式 |
|---|---|---|
| `import 模块名` | `import random, os` | `random.randint(10, 100)` |
| `import 模块名 as 别名` | `import random as rd` | `rd.randint(10, 100)` |
| `from 模块名 import 功能名` | `from random import randint` | `randint(10, 100)` |
| `from 模块名 import 功能名 as 别名` | `from random import randint as rint` | `rint(10, 100)` |
| `from 模块名 import *` | `from random import *` | `randint(10, 100)` |

> 导入语句一般写在 `.py` 文件**开头**。

## 5.3 自定义模块

每个 Python 文件都可作为模块，**模块名就是文件名**（建议用合法标识符规范命名）。

复杂项目拆分为多个模块，让结构更清晰、便于维护与复用：

```
project/
├── config.py       # 配置项
├── session.py      # 会话读写
└── ai_partner.py   # 主逻辑：from session import load_session, save_session
```

## 5.4 `__all__` 与 `__name__`

```python
# my.py
__all__ = ["log_separator1", "log_separator3", "PI"]   # 控制 from my import * 导入哪些功能
PI = 3.1415926
```

- `__all__` **只控制 `from ... import *`**，不影响 `from ... import 具体功能`

```python
if __name__ == "__main__":
    main()
```

| 运行方式 | `__name__` 的值 |
|---|---|
| 模块被**直接运行** | `"__main__"` |
| 模块被**导入** | 模块文件名（不含 `.py` 后缀） |

## 5.5 包（package）

**包 = 文件夹 + `__init__.py`**，里面可以放若干模块。作用：模块多了，用包归类管理（**包的本质也是一个模块**）。

```
utils/
├── __init__.py      # 标识这是包；用 __all__ 控制 import * 时可导入的模块
├── my_var.py
├── my_config.py
└── my_fun.py
```

```python
__all__ = ["my_fun", "my_var"]      # 写在 __init__.py 中
```

| 导入形式 | 示例 | 调用方式 |
|---|---|---|
| `import 包名.模块名` | `import utils.my_fun` | `utils.my_fun.log_separator1()` |
| `from 包名 import 模块名` | `from utils import my_fun` | `my_fun.log_separator1()` |
| `from 包名 import *` | `from utils import *` | `my_fun.log_separator1()` |
| `from 包名.模块名 import 功能名` | `from utils.my_fun import log_separator1` | `log_separator1()` |
| `from 包名.模块名 import *` | `from utils.my_fun import *` | `log_separator1()` |

---

# 06 面向对象基础

## 6.1 两种编程思想

| 思想 | 核心 | 关注点 | 适用 |
|---|---|---|---|
| 面向过程 | 把需求拆成一系列步骤，依次执行 | 流程、步骤 | 简单、线性的任务 |
| 面向对象 | 把特征（属性）和功能（方法）打包成对象 | **谁来做这件事** | 复杂、需复用扩展的系统 |

> 面向过程 = 亲自动手做手工，自己指挥每个动作；面向对象 = 管理一个团队，把任务分配给不同对象。

## 6.2 类与对象

- **类**：一组具有相同属性和方法对象的**模板**
- **对象**：类的**实例**；由类创建出来的过程叫**实例化**，一个类可以创建无数个对象

```python
class 类名:                      # 大驼峰命名法：UserInfo、UserAccount
    pass

对象名 = 类名()                   # 创建对象（实例化）
c1.brand = "BMW"                 # 动态添加属性（不推荐）
print(c1.__dict__)               # 以字典形式查看对象属性
```

## 6.3 `__init__` 与 `self`（推荐写法）

```python
class Car:
    def __init__(self, c_brand, c_name, c_price):
        self.brand = c_brand      # 定义时指定实例属性
        self.name = c_name
        self.price = c_price

c1 = Car("BMW", "X5", 500000)     # 创建对象即传参
```

- `__init__`：初始化方法，**对象创建后自动调用**，用于设置对象初始状态
- `self`：方法的第一个参数，表示**当前实例对象**；**调用时无需传递**
- 定义在类外面的叫**函数**，定义在类里面的叫**方法**

## 6.4 实例方法

```python
class Car:
    def __init__(self, brand, name, price):
        self.brand, self.name, self.price = brand, name, price

    def running(self):
        print(f"{self.brand} {self.name} 正在高速行驶...")

    def total_cost(self, discount, rate):
        return self.price * discount + self.price * rate

c1 = Car("BMW", "X5", 500000)
c1.running()                      # 通过对象调用，self 自动传入
```

## 6.5 魔法方法

以双下划线开头和结尾的特殊方法，**无需手动调用**，Python 在合适时机自动调用。

| 魔法方法 | 描述 |
|---|---|
| `__init__` | 初始化方法 |
| `__str__` | 字符串表示（否则 `print(对象)` 输出内存地址） |
| `__eq__` | 定义两个对象"相等"的规则（默认按内存地址比较） |
| `__lt__` `__le__` `__gt__` `__ge__` | 定义对象大小比较（默认自定义对象不可比大小） |

```python
def __str__(self):
    return f"{self.brand} {self.name} {self.price}"

def __eq__(self, other):
    return self.price == other.price and self.brand == other.brand

def __lt__(self, other):
    return self.price < other.price
```

## 6.6 实例属性 vs 类属性

```python
class Car:
    wheel = 4            # 类属性：所有实例共享
    tax_rate = 0.1

    def __init__(self, c_brand, c_name, c_price):
        self.brand = c_brand    # 实例属性：每个对象独立
```

- 实例属性 → 通过 `实例对象.属性` 操作
- 类属性 → 通过 `类名.属性` 操作
- ⚠️ 通过实例查找属性时：**先找实例属性，不存在时再找类属性**

## 6.7 异常

**异常**：程序运行中出现的错误，会中断正常执行流程。常见：`NameError`、`TypeError`、`IndexError`、`KeyError`、`ValueError`。

> 异常不是坏东西，而是编写**健壮程序**的重要工具。

```python
try:
    可能出现异常的业务代码
except [异常类型 as 变量名]:        # 出现异常时的预案
    处理逻辑
finally:                            # 可选：无论是否异常都会执行（常用于释放资源）
    释放资源
```

```python
try:
    print(my_name)
except NameError as e:
    print("程序运行报错, 错误信息: ", e)
finally:
    print("释放资源 ~")
```

**异常的传递**：异常在函数调用中**层层上报**，直到有人处理它，或者程序崩溃。

```python
def fun1(): fun2()
def fun2(): fun3()
def fun3(): print(my_color)     # 异常从 fun3 → fun2 → fun1 逐层抛出
```

---

# 附录：高频易错点清单

| # | 易错点 | 正确做法 |
|---|---|---|
| 1 | `input()` 返回的是字符串 | 参与计算前先 `int()` / `float()` |
| 2 | 字符串与非字符串用 `+` 拼接报错 | 先 `str(..)`，或直接改用 f-string |
| 3 | 忘了条件后的冒号 `:`、忘了缩进 | 条件/循环/函数/类声明后都要 `:`；代码块缩进 4 空格 |
| 4 | 浮点运算结果不准（如 `0.1+0.2`） | 二进制无法精确表示小数，必要时用 `round()` |
| 5 | `10 / 5` 得到 `2.0` | 要整数结果用 `//` |
| 6 | `range(1, 100)` 取不到 100 | 左闭右开，应写 `range(1, 101)` |
| 7 | while 循环写成死循环 | 必须有使条件变为 False 的语句 |
| 8 | 列表/字典索引越界、字典按索引取值 | 字典**没有下标**，只能按 key 取值 |
| 9 | 空集合写成 `{}` | 那是空字典，空集合是 `set()` |
| 10 | 单元素元组写成 `('A')` | 必须加逗号：`('A',)` |
| 11 | 试图修改字符串/元组元素 | 二者**不可变**，需重新生成 |
| 12 | 默认参数放在普通参数前面 | 默认参数必须在**最后** |
| 13 | 位置参数写在关键字参数后面 | 位置参数必须**在前** |
| 14 | 在函数内直接改全局变量 | 先 `global 变量名` 声明（先声明再使用） |
| 15 | 多返回值用单个变量接收 | 会被封装成元组，用解包 `a, b = fun()` |
| 16 | 以为类型注解会强制校验 | Python 不强制，只是提示 |
| 17 | `print(对象)` 输出内存地址 | 定义 `__str__` |
| 18 | 自定义对象用 `==` 比较结果不符预期 | 默认比内存地址，需定义 `__eq__` |

---

# 附录：一页速查 Cheat Sheet

```python
# —— 输入输出 ——
x = int(input("请输入：")); print(f"结果是 {x}")

# —— 分支 ——
if a > b: ...
elif a == b: ...
else: ...

match cmd:
    case "w" | "W": ...
    case _: ...

# —— 循环 ——
for i in range(1, 101): ...
while flag: ... else: ...
break / continue

# —— 容器 ——
lst = [1, 2, 3];  lst.append(4);  lst[0];  lst[::-1]
s   = "Python";   s.upper(); s.split(","); s.strip()
t   = (1, 2, 3);  a, b, c = t;  a, b = b, a
st  = {1, 2, 3};  st & st2;  st | st2;  st - st2
d   = {"a": 1};   d["b"] = 2;  d.get("a");  d.items()

# —— 函数 ——
def f(a, b=1, *args, **kwargs) -> int:
    """文档字符串"""
    return a + b

g = lambda x: x * 2

# —— 模块 ——
import os
from utils.my_fun import log_separator1
if __name__ == "__main__": main()

# —— 类 ——
class Car:
    wheel = 4                       # 类属性
    def __init__(self, brand):      # 初始化
        self.brand = brand          # 实例属性
    def __str__(self): return self.brand

# —— 异常 ——
try: ...
except ValueError as e: ...
finally: ...
```
