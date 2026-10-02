# Flutter 多端开发复习

> Flutter 是 Google 推出的开源 UI 工具包，使用 Dart 语言，可从一套代码编译为移动（Android/iOS）、Web、桌面（Windows/macOS/Linux）多端原生应用。本文档系统整理 Flutter 核心：架构原理、Dart 语言、Widget 体系、布局、路由、状态管理、网络、存储、动画、平台通道、多端适配、性能优化与发布。

## 一、Flutter 概述与架构

### 1.1 Flutter 核心特性

| 特性 | 说明 |
| --- | --- |
| 单码多端 | 一套 Dart 代码编译为多端原生应用 |
| 自绘渲染 | 不依赖平台原生控件，使用 Skia / Impeller 直接绘制 |
| 热重载 | Hot Reload 保留状态秒级生效，提升开发效率 |
| 声明式 UI | 通过 Widget 树描述界面，状态变化触发重建 |
| 高性能 | 60/120fps，Dart AOT 编译为机器码 |
| 空安全 | Dart 2.12 起支持健全空安全（sound null safety） |

### 1.2 与其他跨端方案对比

| 方案 | 渲染方式 | 语言 | 性能 | 生态 |
| --- | --- | --- | --- | --- |
| Flutter | 自绘（Skia/Impeller） | Dart | 接近原生 | 丰富 |
| React Native | 映射原生组件 | JS/TS | 较好 | 非常丰富 |
| WebView/Hybrid | WebView 渲染 | HTML/CSS/JS | 一般 | Web 生态 |
| Kotlin Multiplatform | 共享逻辑 + 原生 UI | Kotlin | 接近原生 | 发展中 |
| Uni-app | WebView / Weex | Vue | 一般 | 国内丰富 |

> ⚠️ **易错点**：Flutter 不使用平台原生控件，所以 iOS/Android 上 UI 表现一致；而 RN 是映射到原生组件，两端表现可能不同。

### 1.3 Flutter 架构分层

```
┌──────────────────────────────────────────┐
│  Framework (Dart)                         │
│  ┌──────────────────────────────────────┐ │
│  │ Material / Cupertino (组件库)         │ │
│  ├──────────────────────────────────────┤ │
│  │ Widgets（声明式 UI 描述）             │ │
│  ├──────────────────────────────────────┤ │
│  │ Rendering（RenderObject 布局/绘制）   │ │
│  ├──────────────────────────────────────┤ │
│  │ Painting / Gestures / Animation      │ │
│  ├──────────────────────────────────────┤ │
│  │ Foundation（核心工具）                │ │
│  └──────────────────────────────────────┘ │
├──────────────────────────────────────────┤
│  Engine (C++)                             │
│  Skia / Impeller、Dart 运行时、文本布局    │
├──────────────────────────────────────────┤
│  Embedder (平台特定)                       │
│  Android / iOS / Windows / macOS / Linux / Web │
└──────────────────────────────────────────┘
```

- **Framework**：纯 Dart 实现，开发者直接使用
- **Engine**：C++ 实现，负责渲染、文本、Dart VM（JIT/AOT）
- **Embedder**：各平台宿主层，处理事件循环、线程、渲染表面

### 1.4 三棵树（核心原理）

| 树 | 说明 | 是否可变 |
| --- | --- | --- |
| Widget Tree | 不可变的 UI 描述（配置信息） | 不可变（每次重建生成新对象） |
| Element Tree | Widget 的实例，管理生命周期、父子关系 | 可变（diff 后复用） |
| RenderObject Tree | 真正负责测量、布局、绘制 | 可变 |

> 💡 **面试题**：状态改变时 Flutter 如何更新 UI？
> 答：调用 `setState` 标记 Element 为 dirty → 框架触发 `build` 生成新 Widget → 与旧 Widget 毃较（`canUpdate`，看 `runtimeType` 与 `key`）→ 复用 Element，更新 RenderObject → 重新布局绘制。

### 1.5 环境搭建与常用命令

```bash
# 安装 SDK（或下载官方 zip 配置 PATH）
# 配置国内镜像（中国用户建议）
# Windows: 环境变量 FLUTTER_STORAGE_BASE_URL / PUB_HOSTED_URL
#   FLUTTER_STORAGE_BASE_URL=https://storage.flutter-io.cn
#   PUB_HOSTED_URL=https://pub.flutter-io.cn

flutter --version          # 查看版本
flutter doctor             # 检查环境
flutter create my_app      # 创建项目
flutter create --org com.example --platforms=android,ios,web my_app
flutter run                # 运行（debug 默认）
flutter run --release      # 以 release 模式运行
flutter pub get            # 拉取依赖
flutter pub add dio        # 添加依赖
flutter pub upgrade        # 升级依赖
flutter build apk         # 构建 Android APK
flutter build ios          # 构建 iOS
flutter build web          # 构建 Web
flutter clean              # 清理构建产物
```

> ⚠️ **易错点**：
> - **Hot Reload**（按 `r`）：保留 State，仅重新构建 Widget 树；`main()` 与全局变量改动不会被重载。
> - **Hot Restart**（按 `R`）：重启应用，State 与全局变量重置。

---

## 二、Dart 语言核心

### 2.1 变量与类型

```dart
// 变量声明
var name = 'Dart';        // 类型推断：String
final age = 18;           // 运行时常量（只能赋值一次）
const PI = 3.14;          // 编译期常量
late String description;  // 延迟初始化（使用前必须赋值）
int? nullableValue;       // 可空类型（可能为 null）

// 基本类型
int count = 10;           // 64 位整数
double price = 9.99;      // IEEE 754 双精度
bool isTrue = true;
String text = 'hello';
// num 是 int 和 double 的父类
num x = 10;
x = 10.5;
```

| 关键字 | 说明 |
| --- | --- |
| `var` | 类型推断，一旦确定不可变类型 |
| `final` | 运行时常量，只能赋值一次 |
| `const` | 编译期常量，更深层的不可变 |
| `late` | 延迟初始化，使用前必须赋值 |
| `?` | 类型可空标识，如 `int?` |

> ⚠️ **易错点**：
> - `final` 与 `const` 区别：`const` 必须是编译期可确定的值；`final List` 内容仍可修改，`const List` 内容不可修改。
> - `int` / `double` 在 Web 平台编译为 JS Number，存在精度差异（如大整数）。

### 2.2 空安全（Sound Null Safety）

```dart
// 声明可空
String? name;
print(name?.length);     // null 短路：name 为 null 时返回 null
print(name!.length);     // 非空断言：name 为 null 抛异常
String s = name ?? '默认'; // null 合并

// late 用法
class User {
  late final String id = _generateId(); // 首次访问才初始化
  String _generateId() => 'uid-${DateTime.now().millisecondsSinceEpoch}';
}
```

### 2.3 函数

```dart
// 必填参数
int add(int a, int b) => a + b;

// 可选命名参数（推荐，使用 {}）
void greet({required String name, int age = 18}) {
  print('$name, $age');
}
greet(name: 'Tom', age: 20);

// 可选位置参数（使用 []）
String say(String from, [String? to, String? msg]) => '$from -> $to: $msg';

// 箭头函数
var list = [1, 2, 3];
list.forEach((e) => print(e));

// 匿名函数
var square = (int x) => x * x;
```

| 参数类型 | 语法 | 说明 |
| --- | --- | --- |
| 必填参数 | `(int a)` | 调用时必须传入 |
| 可选命名参数 | `({int a, required int b})` | 命名传入，可加默认值或 required |
| 可选位置参数 | `([int a, int b])` | 按位置传入 |

### 2.4 集合

```dart
// List（有序可重复）
List<int> nums = [1, 2, 3];
var spread = [...nums, 4, 5];          // 展开运算符
var nullableSpread = [...?nullableList]; // 展开可空

// Set（无序不重复）
Set<String> names = {'a', 'b', 'a'};   // 结果 {'a', 'b'}

// Map（键值对）
Map<String, int> scores = {'math': 90, 'english': 85};
scores['chinese'] = 88;

// 常用操作
nums.map((e) => e * 2).toList();       // [2, 4, 6]
nums.where((e) => e > 1).toList();     // [2, 3]
nums.any((e) => e > 2);                // true
nums.every((e) => e > 0);              // true
```

### 2.5 类与对象

```dart
class Person {
  String name;
  int age;

  // 构造函数简写
  Person(this.name, this.age);

  // 命名构造函数
  Person.guest() : name = 'guest', age = 0;

  // 命名参数构造函数
  Person.named({required this.name, this.age = 18});

  // getter / setter
  String get description => '$name($age)';
  set setAge(int value) => age = value;

  // 方法
  void speak() => print('I am $name');
}

// 继承
class Student extends Person {
  String school;
  Student(String name, int age, this.school) : super(name, age);

  @override
  void speak() {
    super.speak();
    print('from $school');
  }
}

// 抽象类
abstract class Animal {
  void makeSound();        // 抽象方法
  void breathe() => print('breathing'); // 具体方法
}

// 接口（Dart 中每个类都是隐式接口，用 implements）
class Dog implements Animal {
  @override
  void makeSound() => print('wang');
  @override
  void breathe() => print('dog breathing'); // 必须重写所有成员
}

// Mixin（多重复用）
mixin Flyable {
  void fly() => print('flying');
}
class Bird extends Animal with Flyable {
  @override
  void makeSound() => print('ji');
}
```

| 概念 | 关键字 | 说明 |
| --- | --- | --- |
| 继承 | `extends` | 单继承，复用父类实现 |
| 接口 | `implements` | 必须重写所有成员，不复用实现 |
| Mixin | `with` | 多重混入，复用代码 |

> ⚠️ **易错点**：Dart 没有真正的"接口"关键字，任何类都可作为接口被 `implements`；`with` 用于 mixin，mixin 不能有构造函数。

### 2.6 异步编程

```dart
// Future
Future<String> fetchData() async {
  await Future.delayed(Duration(seconds: 1));
  return 'data';
}

// 调用
void main() async {
  String result = await fetchData();
  print(result);
}

// Stream（流，多次事件）
Stream<int> countDown(int from) async* {
  while (from > 0) {
    await Future.delayed(Duration(seconds: 1));
    yield from--;
  }
}

// 监听 Stream
countDown(3).listen((e) => print(e));

// async / async*
// async 返回 Future，async* 返回 Stream，用 yield 产出值
```

| 概念 | 说明 |
| --- | --- |
| `Future` | 一次性异步结果，对应 Promise |
| `Stream` | 多次异步事件序列，对应 Observable |
| `async` / `await` | 异步语法糖，只能在 async 函数中 |
| `async*` / `yield` | 异步生成器，产出 Stream |

### 2.7 泛型

```dart
// 泛型类
class Stack<T> {
  final List<T> _items = [];
  void push(T item) => _items.add(item);
  T pop() => _items.removeLast();
}

// 泛型方法
T firstOf<T>(List<T> list) => list.first;

// 泛型约束
class Repository<T extends num> {
  final T value;
  Repository(this.value);
}
```

### 2.8 枚举与扩展

```dart
// 枚举（Dart 2.17+ 增强枚举）
enum Color { red, green, blue }

enum HttpStatus {
  ok(200, 'OK'),
  notFound(404, 'Not Found');

  final int code;
  final String message;
  const HttpStatus(this.code, this.message);
}

// 扩展方法
extension StringExtension on String {
  String capitalize() =>
      isEmpty ? this : '${this[0].toUpperCase()}${substring(1)}';
}
'hello'.capitalize(); // 'Hello'
```

> 💡 **面试题**：Dart 是 JIT 还是 AOT？
> 答：开发期使用 JIT（Just-In-Time）支持热重载，发布期使用 AOT（Ahead-Of-Time）编译为机器码，性能接近原生。

---

## 三、Widget 体系

### 3.1 Widget 基础

Widget 是 Flutter UI 的基本描述单元，是不可变的配置信息。`build` 方法返回子 Widget 树。

```dart
import 'package:flutter/material.dart';

void main() => runApp(const MyApp());

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Flutter Demo',
      theme: ThemeData(primarySwatch: Colors.blue),
      home: const HomePage(),
    );
  }
}
```

### 3.2 StatelessWidget vs StatefulWidget

| 类型 | 特点 | 适用场景 |
| --- | --- | --- |
| StatelessWidget | 不可变，`build` 仅依赖外部参数，无内部状态 | 静态展示、纯展示组件 |
| StatefulWidget | 有可变 State，可通过 `setState` 触发重建 | 计数器、表单、动画、需交互更新 UI |

```dart
// 无状态组件
class Greeting extends StatelessWidget {
  final String name;
  const Greeting({super.key, required this.name});

  @override
  Widget build(BuildContext context) {
    return Text('Hello, $name');
  }
}

// 有状态组件
class Counter extends StatefulWidget {
  const Counter({super.key});

  @override
  State<Counter> createState() => _CounterState();
}

class _CounterState extends State<Counter> {
  int _count = 0;

  void _increment() {
    setState(() {
      _count++;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Text('$_count'),
        ElevatedButton(onPressed: _increment, child: const Text('+1')),
      ],
    );
  }
}
```

> ⚠️ **易错点**：
> - `build` 方法可能被框架频繁调用，**不要在其中执行副作用**（如网络请求、修改状态）。
> - `setState` 只能在 State 类内部调用，且应在异步完成前判断 `mounted`。

### 3.3 StatefulWidget 生命周期

```
createState()              // 创建 State 对象
   ↓
initState()                // 只调用一次：初始化数据、订阅事件、控制器
   ↓
didChangeDependencies()    // 依赖变化时调用（如 InheritedWidget 变化）
   ↓
build()                    // 构建界面（可被多次调用）
   ↓
didUpdateWidget(oldWidget) // 父 Widget 重建时调用
   ↓
setState() ─→ build()      // 状态改变触发重建
   ↓
deactivate()               // 从树中被移除时
   ↓
dispose()                  // 释放资源：取消订阅、销毁控制器
```

```dart
class _LifecycleState extends State<LifecycleDemo> {
  @override
  void initState() {
    super.initState();
    print('initState');
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    print('didChangeDependencies');
  }

  @override
  void didUpdateWidget(covariant LifecycleDemo oldWidget) {
    super.didUpdateWidget(oldWidget);
    print('didUpdateWidget');
  }

  @override
  void dispose() {
    print('dispose');
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => const SizedBox();
}
```

### 3.4 App 生命周期

```dart
class _MyAppState extends State<MyApp> with WidgetsBindingObserver {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    switch (state) {
      case AppLifecycleState.resumed:    // 前台可响应
        break;
      case AppLifecycleState.inactive:   // 前台不响应（如来电）
        break;
      case AppLifecycleState.paused:     // 后台
        break;
      case AppLifecycleState.detached:   // 仍运行但宿主分离
        break;
      case AppLifecycleState.hidden:     // 后台但可见（Flutter 3.13+）
        break;
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }
}
```

### 3.5 Key 与 BuildContext

- **Key**：Widget 的身份标识，用于 `canUpdate` 判断是否复用 Element。同层级列表项变动时需要 `ValueKey` 或 `UniqueKey`。
- **GlobalKey**：全局唯一，可跨树访问 Element / State。
- **BuildContext**：本质是 Element，用于向上查找祖先（如 Theme、MediaQuery、Navigator、InheritedWidget）。

```dart
// ValueKey 用法
ListView(
  children: items.map((e) => ListTile(
    key: ValueKey(e.id),
    title: Text(e.name),
  )).toList(),
);

// 获取祖先
final theme = Theme.of(context);
final size = MediaQuery.of(context).size;
```

> ⚠️ **易错点**：`BuildContext.of(context)` 必须在 `build` 中调用，不能在异步后直接用旧的 context（可能导致查找错误或 `dependOnInheritedWidgetWithExactMarked` 异常）。

### 3.6 常用基础 Widget

| 类别 | Widget |
| --- | --- |
| 文本 | `Text`、`RichText`、`TextSpan`、`DefaultTextStyle` |
| 图片 | `Image.network`、`Image.asset`、`Icon`、`CircleAvatar` |
| 容器 | `Container`、`SizedBox`、`Padding`、`DecoratedBox`、`ClipRRect` |
| 按钮 | `ElevatedButton`、`TextButton`、`OutlinedButton`、`FloatingActionButton`、`IconButton` |
| 输入 | `TextField`、`TextFormField`、`Checkbox`、`Switch`、`Slider` |
| 滚动 | `ListView`、`GridView`、`CustomScrollView`、`SingleChildScrollView` |
| Material | `Scaffold`、`AppBar`、`BottomNavigationBar`、`Drawer`、`SnackBar` |

```dart
Scaffold(
  appBar: AppBar(title: const Text('Title')),
  body: const Center(child: Text('Hello')),
  floatingActionButton: FloatingActionButton(
    onPressed: () {},
    child: const Icon(Icons.add),
  ),
  bottomNavigationBar: BottomNavigationBar(
    items: const [
      BottomNavigationBarItem(icon: Icon(Icons.home), label: 'Home'),
      BottomNavigationBarItem(icon: Icon(Icons.person), label: 'Me'),
    ],
  ),
)
```

---

## 四、布局系统

### 4.1 线性布局 Row / Column

| 属性 | 说明 |
| --- | --- |
| `mainAxisAlignment` | 主轴对齐（Row 为水平，Column 为垂直） |
| `crossAxisAlignment` | 交叉轴对齐 |
| `mainAxisSize` | 主轴尺寸（`max` 占满 / `min` 紧凑） |

```dart
Row(
  mainAxisAlignment: MainAxisAlignment.spaceAround,
  crossAxisAlignment: CrossAxisAlignment.center,
  children: [
    Text('A'),
    Text('B'),
    Text('C'),
  ],
)
```

> ⚠️ **易错点**：Row 子项超出屏幕宽度会报 `RenderFlex overflowed` 黄黑条纹，需用 `Expanded` / `Flexible` 或 `SingleChildScrollView` 包裹。

### 4.2 弹性布局 Flex / Expanded / Flexible

```dart
Row(
  children: [
    Expanded(flex: 1, child: Container(color: Colors.red)),    // 占 1 份
    Expanded(flex: 2, child: Container(color: Colors.blue)),   // 占 2 份
    Flexible(
      flex: 1,
      fit: FlexFit.loose,  // loose 不强制占满，tight 强制占满
      child: Container(color: Colors.green),
    ),
  ],
)
```

- `Expanded`：等价于 `Flexible(fit: FlexFit.tight)`，强制填满剩余空间。
- `Flexible`：可选择 `tight` / `loose`。

### 4.3 层叠布局 Stack

```dart
Stack(
  alignment: Alignment.center,
  children: [
    Container(color: Colors.grey, width: 200, height: 200),
    Positioned(
      top: 10,
      right: 10,
      child: Icon(Icons.star, color: Colors.yellow),
    ),
    const Text('Layer'),
  ],
)
```

### 4.4 Container

```dart
Container(
  width: 100,
  height: 100,
  margin: const EdgeInsets.all(8),
  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
  decoration: BoxDecoration(
    color: Colors.blue,
    borderRadius: BorderRadius.circular(8),
    border: Border.all(color: Colors.black, width: 1),
    boxShadow: const [
      BoxShadow(color: Colors.black26, blurRadius: 4, offset: Offset(2, 2)),
    ],
    gradient: const LinearGradient(
      colors: [Colors.red, Colors.blue],
    ),
  ),
  child: const Text('box'),
)
```

> ⚠️ **易错点**：`Container` 同时设置 `color` 与 `decoration` 会报错，颜色应放在 `decoration.color` 中。

### 4.5 响应式尺寸

| Widget | 作用 |
| --- | --- |
| `MediaQuery.of(context).size` | 获取屏幕尺寸 |
| `LayoutBuilder` | 父约束变化时重建 |
| `FractionallySizedBox` | 按比例占父宽高 |
| `AspectRatio` | 保持宽高比 |
| `FittedBox` | 子内容缩放适配 |
| `IntrinsicHeight/Width` | 让子项按内容自适应（性能差，慎用） |

```dart
LayoutBuilder(
  builder: (context, constraints) {
    if (constraints.maxWidth > 600) {
      return const WideLayout();
    }
    return const NarrowLayout();
  },
)
```

---

## 五、列表与滚动

### 5.1 ListView

```dart
// 静态列表（少量数据）
ListView(
  children: const [
    ListTile(title: Text('A')),
    ListTile(title: Text('B')),
  ],
)

// 动态列表（推荐 builder，懒加载）
ListView.builder(
  itemCount: 1000,
  itemBuilder: (context, index) => ListTile(
    title: Text('Item $index'),
  ),
)

// 分离器列表
ListView.separated(
  itemCount: 100,
  separatorBuilder: (_, __) => const Divider(),
  itemBuilder: (context, index) => ListTile(title: Text('Item $index')),
)
```

> ⚠️ **易错点**：直接使用 `ListView(children: [...])` 会一次性构建所有子项，数据量大时内存暴涨；应使用 `ListView.builder` 懒加载。

### 5.2 GridView

```dart
GridView.builder(
  gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
    crossAxisCount: 3,           // 每行 3 列
    mainAxisSpacing: 8,          // 主轴间距
    crossAxisSpacing: 8,         // 交叉轴间距
    childAspectRatio: 1,         // 子项宽高比
  ),
  itemCount: 30,
  itemBuilder: (context, index) => Container(color: Colors.blue),
)
```

### 5.3 CustomScrollView 与 Sliver

Sliver 是 CustomScrollView 的可组合滚动单元，可实现复杂滚动效果（吸顶、视差等）。

```dart
CustomScrollView(
  slivers: [
    SliverAppBar(
      pinned: true,                        // 吸顶
      expandedHeight: 200,
      flexibleSpace: const FlexibleSpaceBar(
        title: Text('Title'),
        background: Icon(Icons.person, size: 80),
      ),
    ),
    SliverList(
      delegate: SliverChildBuilderDelegate(
        (context, index) => ListTile(title: Text('Item $index')),
        childCount: 50,
      ),
    ),
    SliverGrid(
      gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
        crossAxisCount: 2,
      ),
      delegate: SliverChildBuilderDelegate(
        (context, index) => Container(color: Colors.amber),
        childCount: 20,
      ),
    ),
  ],
)
```

### 5.4 下拉刷新与上拉加载

```dart
RefreshIndicator(
  onRefresh: () async {
    await Future.delayed(const Duration(seconds: 1));
    // 重新加载数据
  },
  child: ListView.builder(
    itemCount: items.length,
    itemBuilder: (context, index) {
      if (index == items.length - 1) {
        _loadMore();   // 触底加载
      }
      return ListTile(title: Text(items[index]));
    },
  ),
)
```

---

## 六、路由与导航

### 6.1 Navigator 1.0（命令式）

```dart
// push / pop
Navigator.push(
  context,
  MaterialPageRoute(builder: (context) => const DetailPage()),
);

Navigator.pop(context, 'result');  // 返回并传值

// 接收返回值
final result = await Navigator.push(...);

// 命名路由（在 MaterialApp 中配置）
MaterialApp(
  routes: {
    '/': (context) => const HomePage(),
    '/detail': (context) => const DetailPage(),
  },
);
Navigator.pushNamed(context, '/detail', arguments: {'id': 1});

// 在目标页取参数
final args = ModalRoute.of(context)!.settings.arguments as Map;
```

### 6.2 go_router（声明式路由，官方推荐）

`pubspec.yaml` 添加：`go_router: ^latest`

```dart
import 'package:go_router/go_router.dart';

final router = GoRouter(
  routes: [
    GoRoute(path: '/', builder: (context, state) => const HomePage()),
    GoRoute(
      path: '/detail/:id',
      builder: (context, state) =>
          DetailPage(id: state.pathParameters['id']!),
    ),
  ],
);

MaterialApp.router(routerConfig: router);

// 跳转
context.go('/detail/123');    // 替换栈
context.push('/detail/123');  // 入栈
context.pop();                // 出栈
```

| 操作 | Navigator 1.0 | go_router |
| --- | --- | --- |
| 入栈 | `Navigator.push` | `context.push` |
| 出栈 | `Navigator.pop` | `context.pop` |
| 替换 | `Navigator.pushReplacement` | `context.replace` |
| 清栈到根 | `Navigator.pushNamedAndRemoveUntil` | `context.go` |
| Web URL 同步 | 不支持 | 自动同步 |

> 💡 **面试题**：Navigator 1.0 与 2.0 区别？
> 答：1.0 是命令式（push/pop），简单但不支持 Web URL 同步；2.0 是声明式（Pages API），可同步 URL、支持深链接，go_router 是官方封装的易用版本。

---

## 七、状态管理

### 7.1 状态管理方案对比

| 方案 | 复杂度 | 特点 | 适用场景 |
| --- | --- | --- | --- |
| `setState` | 低 | 仅组件内部状态 | 简单局部 UI |
| `InheritedWidget` | 中 | 自上而下共享，性能需手动优化 | 主题、共享只读 |
| `Provider` | 中 | InheritedWidget 封装，简单易用 | 中小型应用 |
| `Riverpod` | 高 | 编译期安全、不依赖 BuildContext | 中大型应用 |
| `Bloc` / `Cubit` | 高 | 事件驱动、Stream、可测试性强 | 大型应用 |
| `GetX` | 低 | 简单、响应式、内置路由与存储 | 快速开发（争议较多） |

### 7.2 Provider 示例

```dart
// 1. 定义 ChangeNotifier
class CounterModel extends ChangeNotifier {
  int _count = 0;
  int get count => _count;

  void increment() {
    _count++;
    notifyListeners();   // 通知依赖者重建
  }
}

// 2. 在顶层提供
void main() {
  runApp(
    ChangeNotifierProvider(
      create: (_) => CounterModel(),
      child: const MyApp(),
    ),
  );
}

// 3. 消费
class CounterWidget extends StatelessWidget {
  const CounterWidget({super.key});

  @override
  Widget build(BuildContext context) {
    // 精细监听，仅 count 变化时重建
    final count = context.select<CounterModel, int>((m) => m.count);
    final model = context.read<CounterModel>();

    return Column(
      children: [
        Text('$count'),
        ElevatedButton(
          onPressed: model.increment,
          child: const Text('+1'),
        ),
      ],
    );
  }
}
```

| API | 说明 |
| --- | --- |
| `Provider.of<T>(context)` | 获取并监听（默认 listen=true） |
| `context.watch<T>()` | 监听整个对象变化 |
| `context.read<T>()` | 只读取不监听（用于回调） |
| `context.select<T, R>(...)` | 监听部分字段，性能更优 |
| `Consumer<T>` | 局部重建 |

### 7.3 Riverpod 示例

```dart
import 'package:flutter_riverpod/flutter_riverpod.dart';

// 定义 Provider
final counterProvider = StateNotifierProvider<Counter, int>((ref) => Counter());

class Counter extends StateNotifier<int> {
  Counter() : super(0);
  void increment() => state++;
}

void main() {
  runApp(const ProviderScope(child: MyApp()));
}

class CounterWidget extends ConsumerWidget {
  const CounterWidget({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final count = ref.watch(counterProvider);
    return ElevatedButton(
      onPressed: ref.read(counterProvider.notifier).increment,
      child: Text('$count'),
    );
  }
}
```

> ⚠️ **易错点**：Riverpod 不依赖 BuildContext，Provider 在编译期可被检测，避免运行时找不到 Provider 的问题。

### 7.4 Bloc / Cubit 示例

```dart
// Cubit（简化版 Bloc，无事件类）
class CounterCubit extends Cubit<int> {
  CounterCubit() : super(0);
  void increment() => emit(state + 1);
}

// Bloc（事件 + 状态）
abstract class CounterEvent {}
class Increment extends CounterEvent {}

class CounterBloc extends Bloc<CounterEvent, int> {
  CounterBloc() : super(0) {
    on<Increment>((event, emit) => emit(state + 1));
  }
}

// 使用
BlocProvider(
  create: (_) => CounterCubit(),
  child: BlocBuilder<CounterCubit, int>(
    builder: (context, state) => Text('$state'),
  ),
)
```

---

## 八、网络请求

### 8.1 http 包（官方）

`pubspec.yaml`：`http: ^latest`

```dart
import 'dart:convert';
import 'package:http/http.dart' as http;

Future<Map<String, dynamic>> fetchUser(int id) async {
  final response = await http.get(
    Uri.parse('https://api.example.com/users/$id'),
    headers: {'Authorization': 'Bearer token'},
  );
  if (response.statusCode == 200) {
    return jsonDecode(response.body) as Map<String, dynamic>;
  }
  throw Exception('Failed: ${response.statusCode}');
}
```

### 8.2 dio（第三方，功能更强）

```dart
import 'package:dio/dio.dart';

final dio = Dio(BaseOptions(
  baseUrl: 'https://api.example.com',
  connectTimeout: const Duration(seconds: 5),
  receiveTimeout: const Duration(seconds: 10),
));

// 拦截器
dio.interceptors.add(InterceptorsWrapper(
  onRequest: (options, handler) {
    options.headers['token'] = 'xxx';
    return handler.next(options);
  },
  onResponse: (response, handler) {
    // 统一处理响应
    return handler.next(response);
  },
  onError: (error, handler) {
    return handler.next(error);
  },
));

// 请求
final response = await dio.get('/users/1');
final data = response.data;

// POST 表单
final formData = FormData.fromMap({'name': 'Tom', 'age': 18});
await dio.post('/users', data: formData);

// 上传文件
final formDataFile = FormData.fromMap({
  'file': await MultipartFile.fromFile('./photo.jpg', filename: 'photo.jpg'),
});
await dio.post('/upload', data: formDataFile);

// 取消请求
final cancelToken = CancelToken();
dio.get('/long', cancelToken: cancelToken);
cancelToken.cancel('用户取消');
```

| 特性 | http | dio |
| --- | --- | --- |
| 基础请求 | ✅ | ✅ |
| 拦截器 | ❌ | ✅ |
| 全局配置 | ❌ | ✅ |
| 取消请求 | ✅（CancelToken 较繁琐） | ✅ |
| 文件上传 | 需手动 | 内置 FormData |
| 自动 JSON 解析 | ❌ | ✅ |

### 8.3 JSON 序列化（推荐 json_serializable）

```dart
// pubspec.yaml: json_annotation, json_serializable, build_runner

import 'package:json_annotation/json_annotation.dart';
part 'user.g.dart';

@JsonSerializable()
class User {
  final int id;
  final String name;
  User({required this.id, required this.name});

  factory User.fromJson(Map<String, dynamic> json) => _$UserFromJson(json);
  Map<String, dynamic> toJson() => _$UserToJson(this);
}

// 生成代码：flutter pub run build_runner build --delete-conflicting-outputs
```

---

## 九、本地存储

### 9.1 SharedPreferences（轻量键值对）

```dart
import 'package:shared_preferences/shared_preferences.dart';

// 写
final prefs = await SharedPreferences.getInstance();
await prefs.setString('token', 'abc');
await prefs.setInt('count', 10);
await prefs.setBool('isLogin', true);

// 读
final token = prefs.getString('token') ?? '';
```

> ⚠️ **易错点**：SharedPreferences 只支持基本类型（`String/int/double/bool/List<String>`），不支持对象；存储需异步，调用 `getInstance()`。

### 9.2 sqflite（SQLite 关系数据库）

```dart
import 'package:sqflite/sqflite.dart';
import 'package:path/path.dart';

Future<Database> openDB() async {
  final path = join(await getDatabasesPath(), 'app.db');
  return openDatabase(
    path,
    version: 1,
    onCreate: (db, v) async {
      await db.execute('''
        CREATE TABLE users(id INTEGER PRIMARY KEY, name TEXT, age INTEGER)
      ''');
    },
  );
}

// 增删改查
final db = await openDB();
await db.insert('users', {'name': 'Tom', 'age': 20});
final list = await db.query('users', where: 'age > ?', whereArgs: [18]);
await db.update('users', {'age': 21}, where: 'id = ?', whereArgs: [1]);
await db.delete('users', where: 'id = ?', whereArgs: [1]);
```

### 9.3 Hive（NoSQL，性能高）

```dart
import 'package:hive/hive.dart';

@HiveType(typeId: 0)
class User extends HiveObject {
  @HiveField(0) String name;
  @HiveField(1) int age;
  User({required this.name, required this.age});
}

var box = await Hive.openBox('settings');
box.put('theme', 'dark');
print(box.get('theme'));   // dark
```

### 9.4 文件存储（path_provider）

```dart
import 'dart:io';
import 'package:path_provider/path_provider.dart';

Future<void> writeFile(String content) async {
  final dir = await getApplicationDocumentsDirectory();
  final file = File('${dir.path}/note.txt');
  await file.writeAsString(content);
}
```

| 方案 | 适用 | 特点 |
| --- | --- | --- |
| `shared_preferences` | 配置、token | 轻量、基本类型 |
| `sqflite` | 结构化数据 | SQLite、支持 SQL |
| `hive` | 高频读写 NoSQL | 性能高、纯 Dart |
| `path_provider` + `dart:io` | 大文件 | 文件系统 |
| `flutter_secure_storage` | 敏感信息 | iOS Keychain / Android EncryptedPrefs |

---

## 十、动画

### 10.1 隐式动画（AnimatedXxx）

简单使用，无需 Controller。

```dart
AnimatedContainer(
  duration: const Duration(milliseconds: 300),
  curve: Curves.easeInOut,
  width: _selected ? 200 : 100,
  height: _selected ? 200 : 100,
  color: _selected ? Colors.blue : Colors.grey,
)
```

| Widget | 作用 |
| --- | --- |
| `AnimatedContainer` | 容器属性过渡 |
| `AnimatedOpacity` | 透明度过渡 |
| `AnimatedAlign` | 位置过渡 |
| `AnimatedSwitcher` | 子项切换过渡 |
| `TweenAnimationBuilder` | 自定义值过渡 |

### 10.2 显式动画（AnimationController）

```dart
class FadeBox extends StatefulWidget {
  const FadeBox({super.key});
  @override
  State<FadeBox> createState() => _FadeBoxState();
}

class _FadeBoxState extends State<FadeBox>
    with SingleTickerProviderStateMixin {
  late AnimationController _controller;
  late Animation<double> _animation;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 1),
    );
    _animation = Tween<double>(begin: 0, end: 1).animate(_controller);
    _controller.forward();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return FadeTransition(
      opacity: _animation,
      child: const FlutterLogo(size: 100),
    );
  }
}
```

> ⚠️ **易错点**：`AnimationController` 必须在 `dispose` 中释放；`vsync: this` 需 `with SingleTickerProviderStateMixin`（单个）或 `TickerProviderStateMixin`（多个）。

### 10.3 Hero 动画（共享元素过渡）

```dart
// 页面 A
Hero(
  tag: 'avatar',
  child: Image.network(url, width: 50),
)

// 页面 B
Hero(
  tag: 'avatar',
  child: Image.network(url, width: 200),
)
```

跳转时自动播放平滑过渡动画，`tag` 必须唯一。

---

## 十一、多端适配与平台特定

### 11.1 平台判断

```dart
import 'dart:io' show Platform;
import 'package:flutter/foundation.dart' show kIsWeb, defaultTargetPlatform;

// Web 平台：dart:io 不可用，必须先判断 kIsWeb
if (kIsWeb) {
  // Web 逻辑
} else if (Platform.isAndroid) {
  // Android
} else if (Platform.isIOS) {
  // iOS
} else if (Platform.isWindows) {
  // Windows
} else if (Platform.isMacOS) {
  // macOS
} else if (Platform.isLinux) {
  // Linux
}

// 使用 defaultTargetPlatform（在 Web 上也可用）
if (defaultTargetPlatform == TargetPlatform.android) {
  // Android 风格
}
```

> ⚠️ **易错点**：Web 平台不能 import `dart:io`（会编译失败），必须用 `kIsWeb` 短路判断。

### 11.2 Material 与 Cupertino 切换

```dart
import 'package:flutter/material.dart';
import 'package:flutter/cupertino.dart';

Widget buildButton() {
  return Platform.isIOS
      ? CupertinoButton(onPressed: () {}, child: const Text('OK'))
      : ElevatedButton(onPressed: () {}, child: const Text('OK'));
}

// 或使用 flutter_platform_widgets 包统一 API
```

### 11.3 响应式布局（断点）

```dart
enum DeviceType { mobile, tablet, desktop }

DeviceType getDeviceType(double width) {
  if (width >= 1200) return DeviceType.desktop;
  if (width >= 600) return DeviceType.tablet;
  return DeviceType.mobile;
}

LayoutBuilder(
  builder: (context, constraints) {
    final type = getDeviceType(constraints.maxWidth);
    // 根据类型返回不同布局
    return ...;
  },
)
```

### 11.4 平台通道（Platform Channel）

用于调用原生 API（Flutter SDK 未覆盖的能力）。

```dart
// Flutter 端
import 'package:flutter/services.dart';

const platform = MethodChannel('com.example.app/battery');

Future<int> getBatteryLevel() async {
  final level = await platform.invokeMethod('getBatteryLevel');
  return level;
}

// Android（Kotlin）
class MainActivity : FlutterActivity() {
  override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
    MethodChannel(flutterEngine.dartExecutor.binaryMessenger, "com.example.app/battery")
      .setMethodCallHandler { call, result ->
        when (call.method) {
          "getBatteryLevel" -> result.success(getBatteryLevel())
          else -> result.notImplemented()
        }
      }
  }
  private fun getBatteryLevel(): Int { /* ... */ return 80 }
}

// iOS（Swift）
let channel = FlutterMethodChannel(
  name: "com.example.app/battery",
  binaryMessenger: controller.binaryMessenger
)
channel.setMethodCallHandler { call, result in
  if call.method == "getBatteryLevel" {
    result(80)
  } else {
    result(FlutterMethodNotImplemented)
  }
}
```

| 通道类型 | 用途 |
| --- | --- |
| `MethodChannel` | 方法调用（请求-响应） |
| `EventChannel` | 事件流（持续监听原生事件） |
| `BasicMessageChannel` | 基本消息传递 |

> ⚠️ **易错点**：平台通道在 Web 端不可用，需另写 Web 实现。

---

## 十二、性能优化

### 12.1 重建优化

| 手段 | 说明 |
| --- | --- |
| 拆分 Widget | 把频繁变化的部分拆为独立 StatefulWidget |
| `const` 构造函数 | 编译期常量，不参与重建 |
| `Consumer` / `Selector` | 局部订阅，避免整树重建 |
| `const` 子项 | `const` 标记的子项在父重建时不会重建 |

```dart
// 推荐：const 复用
const Text('Hello');   // 编译期常量

// 推荐：拆分变化部分
class Parent extends StatelessWidget {
  const Parent({super.key});
  @override
  Widget build(BuildContext context) {
    return Column(
      children: const [
        StaticHeader(),     // 不变
        DynamicCounter(),   // 内部状态变化只重建自己
      ],
    );
  }
}
```

### 12.2 列表优化

```dart
// 推荐：const item + builder + key
ListView.builder(
  itemCount: 1000,
  itemBuilder: (context, index) => _Item(index: index),
)

class _Item extends StatelessWidget {
  final int index;
  const _Item({required this.index});
  @override
  Widget build(BuildContext context) => ListTile(title: Text('Item $index'));
}

// 复杂图片列表：缓存 + 占位
Image.network(
  url,
  cacheWidth: 200,            // 解码到指定尺寸，节省内存
  loadingBuilder: (context, child, progress) =>
      progress == null ? child : const CircularProgressIndicator(),
)
```

### 12.3 工具与检测

| 工具 | 用途 |
| --- | --- |
| Flutter DevTools | 性能 / 内存 / 网络分析 |
| Performance Overlay | 显示每帧耗时 |
| `RepaintBoundary` | 隔离重绘范围 |
| `const` 构造 | 减少重建 |
| `AutomaticKeepAliveClientMixin` | 切换 Tab 时保持状态 |

```dart
// 性能覆盖层
MaterialApp(showPerformanceOverlay: true, home: ...);

// 隔离重绘
RepaintBoundary(
  child: ExpensiveWidget(),
)

// 保活
class _TabPageState extends State<TabPage>
    with AutomaticKeepAliveClientMixin {
  @override
  bool get wantKeepAlive => true;

  @override
  Widget build(BuildContext context) {
    super.build(context);   // 必须调用
    return ...;
  }
}
```

### 12.4 异步隔离 isolate

CPU 密集任务应放到 isolate 中，避免卡 UI 线程。

```dart
// 简单 compute（自动管理 isolate）
// compute(函数, 参数) —— 函数必须是顶层或静态函数
final result = await compute(heavyCompute, 42);

int heavyCompute(int input) {
  // 耗时计算
  return input * 2;
}

// 复杂场景：Isolate.spawn / Isolate.run（Dart 2.19+）
final result = await Isolate.run(() => heavyCompute(42));
```

---

## 十三、构建与发布

### 13.1 构建模式

| 模式 | 命令 | 特点 |
| --- | --- | --- |
| Debug | `flutter run` | JIT、含调试信息、热重载 |
| Profile | `flutter run --profile` | 接近 Release，可调试性能 |
| Release | `flutter run --release` | AOT、优化、无调试 |

### 13.2 Android 打包

```bash
# 1. 配置签名（android/app/build.gradle）
# 2. 生成 keystore
keytool -genkey -v -keystore ~/upload-keystore.jks -keyalg RSA -keysize 2048 -validity 10000 -alias upload

# 3. 构建 APK
flutter build apk --release
flutter build apk --split-per-abi    # 按 ABI 分包，体积更小

# 4. 构建 AAB（Google Play 上传格式）
flutter build appbundle --release
```

### 13.3 iOS 打包

```bash
# 1. 在 Xcode 配置签名（Signing & Capabilities）
# 2. 构建
flutter build ios --release
# 3. 在 Xcode 中 Archive → Distribute
```

> ⚠️ **易错点**：iOS 打包必须使用 macOS + Xcode，Windows / Linux 无法构建 iOS。

### 13.4 Web 打包

```bash
flutter build web --release
# 默认输出在 build/web
# 可选渲染模式：--web-renderer html / canvaskit（Flutter 3.10+ 默认 canvaskit）
```

### 13.5 桌面打包

```bash
flutter build windows --release
flutter build macos --release
flutter build linux --release
```

### 13.6 应用图标与启动屏

```yaml
# 推荐使用 flutter_launcher_icons 与 flutter_native_splash
# pubspec.yaml
dev_dependencies:
  flutter_launcher_icons: ^latest
  flutter_native_splash: ^latest

flutter_icons:
  android: true
  ios: true
  image_path: "assets/icon.png"

flutter_native_splash:
  color: "#ffffff"
  image: assets/splash.png
```

```bash
dart run flutter_launcher_icons
dart run flutter_native_splash:create
```

---

## 十四、常用第三方库

| 类别 | 包名 | 用途 |
| --- | --- | --- |
| 状态管理 | `provider` / `riverpod` / `flutter_bloc` / `get` | 状态共享 |
| 路由 | `go_router` | 声明式路由 |
| 网络 | `dio` | HTTP 客户端 |
| 本地存储 | `shared_preferences` / `hive` / `sqflite` | 持久化 |
| 序列化 | `json_serializable` / `freezed` | JSON 模型生成 |
| 图片缓存 | `cached_network_image` | 网络图片缓存 |
| 图表 | `fl_chart` | 自定义图表 |
| WebView | `webview_flutter` | 内嵌网页 |
| 摄像头 | `camera` / `image_picker` | 相机 / 相册 |
| 定位 | `geolocator` | 地理位置 |
| 推送 | `firebase_messaging` | FCM 推送 |
| 本地通知 | `flutter_local_notifications` | 本地通知 |
| 国际化 | `flutter_localizations` / `intl` | 多语言 |
| 权限 | `permission_handler` | 运行时权限 |
| 平台 UI | `flutter_platform_widgets` | 跨平台统一 UI |
| 测试 | `mockito` / `integration_test` | 单元 / 集成测试 |

---

## 十五、高频面试题速记

### Q1：Flutter 为什么能跨端且高性能？

- 自绘渲染：使用 Skia / Impeller 直接调用底层图形 API（OpenGL/Metal/Vulkan），不依赖平台控件
- Dart AOT：发布时编译为机器码，无 JS Bridge 开销
- 三棵树 diff：Element 复用、只更新变化的 RenderObject

### Q2：StatelessWidget 和 StatefulWidget 区别？何时用哪个？

- Stateless：`build` 仅依赖构造参数，无内部状态，用于纯展示
- Stateful：持有 State，可通过 `setState` 触发重建，用于有交互、有变化的 UI
- 选择原则：能 Stateless 就不用 Stateful，状态提升到最小作用域

### Q3：setState 之后发生了什么？

1. `setState` 内部调用 `markNeedsBuild`，将 Element 标记为 dirty
2. 下一帧调度时框架调用 `build` 生成新 Widget
3. 新旧 Widget 经 `canUpdate`（`runtimeType` + `key`）比较
4. 复用 Element 并更新对应的 RenderObject
5. RenderObject 重新布局 / 绘制并合成到屏幕

### Q4：Hot Reload 与 Hot Restart 区别？

- Hot Reload：注入新代码到运行中的 Dart VM，保留 State，仅重建 Widget 树；不重新执行 `main()`
- Hot Restart：重启应用，重置所有状态与全局变量

### Q5：Provider 与 Riverpod 区别？

- Provider：依赖 InheritedWidget，使用 `BuildContext` 查找，运行时可能报 `ProviderNotFoundException`
- Riverpod：不依赖 BuildContext，编译期可检测，支持多种 Provider 类型，状态可被 dispose

### Q6：Flutter 与 RN 渲染原理区别？

- Flutter：自绘渲染，所有 UI 都由 Skia/Impeller 绘制，跨端一致
- RN：JS 渲染指令通过 Bridge 调用原生组件，两端表现可能不同；新版 Fabric 有改进

### Q7：为什么 Widget 是不可变的？

- Widget 是配置描述，不可变便于 diff 比较（直接对比新旧对象）
- 状态由独立的 State 对象持有，保证数据流清晰
- 不可变对象可被 `const` 优化，减少重建开销

### Q8：Key 的作用？什么时候需要 Key？

- Key 是 Widget 的身份标识，用于 `canUpdate` 判断 Element 是否复用
- 同层级列表中项的位置/顺序会变化（增删、排序）时需要 `ValueKey`
- 全局唯一标识用 `GlobalKey`（可访问 State / 跨树复用，但开销大）

### Q9：const 构造函数的意义？

- 编译期常量，相同参数只创建一个实例
- 父 Widget 重建时，`const` 子项不参与重建，性能更优
- 需要 `const` 构造函数 + 所有字段为 `final`

### Q10：Flutter 内存泄漏常见原因？

- `AnimationController`、`TextEditingController`、`ScrollController` 未在 `dispose` 释放
- Stream / StreamSubscription 未 cancel
- `addListener` 监听未 remove
- `Timer` 未 cancel
- 持有 `BuildContext` 的回调在异步完成后仍调用（导致 Element 已销毁）

---

## 十六、知识体系总览

```
Dart 语言基础 ─┐
               ├─→ Widget 体系（Stateless/Stateful/生命周期）
Flutter 架构 ──┘         │
                          ↓
                  布局系统（Row/Column/Stack/Container）
                          │
              ┌───────────┼───────────┐
              ↓           ↓           ↓
          列表滚动    路由导航    状态管理
        (ListView)  (Navigator)  (Provider/Riverpod/Bloc)
              │           │           │
              └─────┬─────┴─────┬─────┘
                    ↓           ↓
                网络请求     本地存储
               (http/dio) (Prefs/SQLite/Hive)
                    │
                    ↓
              动画 / 平台通道 / 多端适配
                    │
                    ↓
              性能优化 → 构建发布（Android/iOS/Web/Desktop）
```

> 学习路径建议：Dart 语法 → Widget 与布局 → 状态管理 → 路由与网络 → 动画与平台能力 → 多端适配与发布。每个模块动手写 Demo，配合 DevTools 观察性能。
