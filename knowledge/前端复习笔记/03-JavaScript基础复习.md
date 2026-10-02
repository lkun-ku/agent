# JavaScript 基础复习

> JavaScript 是一门运行在浏览器（也可运行在 Node.js）上的脚本语言，负责网页的交互逻辑。本文梳理变量、数据类型、运算符、流程控制、循环、数组、函数、对象等核心基础知识。

## 一、JavaScript 简介

### 1.1 JS 引入方式

| 方式 | 写法 | 说明 |
| --- | --- | --- |
| 内部 JS | 在 HTML 中写 `<script>` 标签 | 适合少量代码 |
| 外部 JS | `<script src="xxx.js"></script>` | 推荐，结构与行为分离 |
| 行内 JS | 直接写在 HTML 标签属性中（如 `onclick`） | 不推荐 |

```html
<!-- 内部 -->
<script>
  console.log('hello')
</script>

<!-- 外部 -->
<script src="./js/main.js"></script>
```

⚠️ **易错点**：`<script>` 标签使用 `src` 引入外部文件后，标签内部的代码会被忽略，不会执行。

### 1.2 注释与结束符

```javascript
// 单行注释

/*
  多行注释
  多行注释
*/

// 结束符：分号 ; （可写可不写，推荐写上）
let a = 1
let b = 2;
```

⚠️ **易错点**：JavaScript 中分号可省略（ASI 自动分号插入机制），但为了代码规范和避免某些解析歧义，建议每条语句结尾加分号。

### 1.3 输入输出

| 方法 | 作用 | 返回值 |
| --- | --- | --- |
| `prompt('提示')` | 弹出输入框 | string 类型（用户输入内容） |
| `alert('内容')` | 弹出警告框 | undefined |
| `document.write('内容')` | 向页面输出内容 | undefined |
| `console.log('内容')` | 控制台输出 | undefined |

```javascript
let name = prompt('请输入你的名字')   // 输入
alert('你好，' + name)                // 输出弹窗
document.write('<h1>页面内容</h1>')    // 输出到页面
console.log('调试信息')               // 控制台输出
```

⚠️ **易错点**：`prompt` 返回值始终是 string，即使用户输入数字，需要参与运算时要先做类型转换。

---

## 二、变量与常量

### 2.1 变量声明

```javascript
let age = 18        // 变量，可重新赋值（推荐）
var name = '张三'   // 旧语法，有设计缺陷
const PI = 3.14     // 常量，必须初始化且不能重新赋值
```

### 2.2 let 与 var 的区别

| 对比项 | `var` | `let` |
| --- | --- | --- |
| 变量提升 | 有（声明提升到作用域顶部，值为 undefined） | 有（暂时性死区，访问会报错） |
| 作用域 | 函数作用域 | 块级作用域 `{}` |
| 重复声明 | 允许 | 不允许，报错 |
| 全局声明挂载到 window | 是 | 否 |

```javascript
// 1. 变量提升
console.log(a)  // undefined（var 提升）
var a = 10

console.log(b)  // ReferenceError（let 暂时性死区）
let b = 10

// 2. 块级作用域
{
  var x = 1
  let y = 2
}
console.log(x)  // 1（var 泄漏到外面）
console.log(y)  // ReferenceError

// 3. 重复声明
var m = 1
var m = 2        // 不报错
let n = 1
let n = 2        // SyntaxError
```

⚠️ **易错点**：现代开发中优先使用 `let`/`const`，避免使用 `var`。

### 2.3 变量命名规范

- 由字母、数字、下划线 `_`、美元符 `$` 组成
- 不能以数字开头
- 严格区分大小写
- 不能使用关键字和保留字（如 `let`、`class`、`return`）
- 建议使用驼峰命名法：`userName`、`getMaxValue`
- 见名知意，避免 `a`、`b`、`x` 等无意义命名

### 2.4 常量 const

```javascript
const PI = 3.14
PI = 3.15  // TypeError: Assignment to constant variable

// const 声明引用类型时，地址不可变，但内部属性可变
const arr = [1, 2, 3]
arr.push(4)      // 允许
arr = [1, 2]     // 报错（重新赋值不允许）
```

⚠️ **易错点**：`const` 声明时必须初始化；对于对象/数组，`const` 锁定的是变量指向的地址，内部成员仍可修改。

---

## 三、数据类型

### 3.1 基本数据类型

| 类型 | 说明 | 示例 |
| --- | --- | --- |
| `number` | 数字（整数、小数、正负数） | `1`、`3.14`、`-5` |
| `string` | 字符串 | `'hello'`、`"world"` |
| `boolean` | 布尔值 | `true`、`false` |
| `undefined` | 未定义（声明未赋值） | `let a;` → `undefined` |
| `null` | 空值（手动赋值，表示"无"） | `let a = null` |

### 3.2 引用数据类型

| 类型 | 说明 | 示例 |
| --- | --- | --- |
| `object` | 对象 | `{name: '张三', age: 18}` |
| `array` | 数组（本质是对象） | `[1, 2, 3]` |
| `function` | 函数（本质是对象） | `function(){}` |

### 3.3 typeof 检测数据类型

```javascript
console.log(typeof 1)           // 'number'
console.log(typeof 'abc')       // 'string'
console.log(typeof true)        // 'boolean'
console.log(typeof undefined)   // 'undefined'
console.log(typeof null)        // 'object'  ⚠️ 历史遗留 bug
console.log(typeof {})          // 'object'
console.log(typeof [])          // 'object'
console.log(typeof function(){})// 'function'
```

⚠️ **易错点**：`typeof null` 返回 `'object'`，这是历史遗留 bug；`typeof` 无法区分数组和普通对象，需用 `Array.isArray()`。

### 3.4 字符串

```javascript
// 引号：单引号、双引号均可，推荐单引号
let s1 = 'hello'
let s2 = "world"

// 转义符
let s3 = 'It\'s me'     // \' 转义单引号
let s4 = '第一行\n第二行' // \n 换行
let s5 = 'a\tb'         // \t 制表符
let s6 = 'C:\\Users'    // \\ 反斜杠

// 模板字符串（反引号 ``）
let name = '张三'
let age = 18
let s7 = `我叫${name}，今年${age}岁`  // 支持变量插值
let s8 = `多行
字符串`                              // 支持换行
```

⚠️ **易错点**：模板字符串必须用反引号 `` ` ``（键盘左上角），变量插值用 `${}`。

### 3.5 NaN 与 isNaN

```javascript
console.log('abc' - 1)   // NaN（Not a Number）
console.log(NaN === NaN) // false（NaN 不等于任何值，包括自己）
console.log(NaN + 1)     // NaN（NaN 参与运算结果仍为 NaN）

// isNaN() 判断是否为 NaN
console.log(isNaN('abc'))   // true
console.log(isNaN(123))     // false
console.log(isNaN('123'))   // false（先转换成数字）
```

---

## 四、类型转换

### 4.1 隐式转换

```javascript
// + 号：只要有字符串就拼接成字符串
console.log(1 + '2')     // '12'
console.log(1 + 2 + '3') // '33'（先 1+2=3，再拼 '3'）
console.log('1' + 2 + 3) // '123'（从左到右，全拼接）

// - * / 号：自动转成数字
console.log('10' - 2)    // 8
console.log('10' * 2)    // 20
console.log('10' / 2)    // 5

// 不同类型比较会隐式转换
console.log('3' > 2)     // true
console.log('3' > '12')  // true ⚠️ 字符串比较按字符编码逐位比较
```

⚠️ **易错点**：`+` 号既可做加法又可做拼接，遇到字符串时一定拼接；字符串比较是按字典序逐字符比较，`'3' > '12'` 为 `true`。

### 4.2 显式转换

| 方法 | 作用 | 示例 |
| --- | --- | --- |
| `Number()` | 转数字，失败返回 NaN | `Number('123')` → `123`，`Number('abc')` → `NaN` |
| `parseInt()` | 转整数（取整，截断小数） | `parseInt('12.5')` → `12`，`parseInt('18px')` → `18` |
| `parseFloat()` | 转小数 | `parseFloat('12.5px')` → `12.5` |
| `String()` | 转字符串 | `String(123)` → `'123'` |
| `Boolean()` | 转布尔值 | `Boolean(0)` → `false`，`Boolean('')` → `false` |
| `变量.toString()` | 转字符串（null/undefined 报错） | `(123).toString()` → `'123'` |

```javascript
console.log(Number('123'))     // 123
console.log(Number('12.5'))    // 12.5
console.log(Number('12px'))    // NaN
console.log(Number(''))        // 0
console.log(Number('  '))      // 0
console.log(Number(true))      // 1
console.log(Number(null))      // 0
console.log(Number(undefined)) // NaN

console.log(parseInt('12.9'))  // 12
console.log(parseInt('12px'))  // 12（自动忽略单位）
console.log(parseInt('px12'))  // NaN（开头非数字）
console.log(parseFloat('12.5px')) // 12.5
```

**Boolean 转换的假值（falsy）：** `false`、`''`、`0`、`null`、`undefined`、`NaN`，其余全为 `true`（包括 `'0'`、`'false'`、`[]`、`{}`）。

⚠️ **易错点**：`Number('')` 是 `0`，但 `Number('abc')` 是 `NaN`；`parseInt` 会忽略末尾的非数字字符。

### 4.3 == 与 === 的区别

| 运算符 | 说明 | 示例 |
| --- | --- | --- |
| `==` | 比较前会做隐式类型转换 | `1 == '1'` → `true`，`null == undefined` → `true` |
| `===` | 全等，类型和值都必须相等 | `1 === '1'` → `false`，`null === undefined` → `false` |
| `!=` | 不等（会转换） | `1 != '1'` → `false` |
| `!==` | 不全等（不转换） | `1 !== '1'` → `true` |

⚠️ **易错点**：实际开发中**永远使用 `===`**，避免 `==` 带来的隐式转换陷阱。

---

## 五、运算符

### 5.1 算术运算符

| 运算符 | 说明 | 示例 |
| --- | --- | --- |
| `+` | 加 / 字符串拼接 | `1 + 2` → `3`，`'1' + 2` → `'12'` |
| `-` | 减 | `5 - 2` → `3` |
| `*` | 乘 | `2 * 3` → `6` |
| `/` | 除 | `6 / 2` → `3` |
| `%` | 取余 | `7 % 3` → `1` |
| `**` | 幂（ES7） | `2 ** 3` → `8` |

### 5.2 赋值运算符

| 运算符 | 等价写法 | 示例 |
| --- | --- | --- |
| `=` | 赋值 | `a = 5` |
| `+=` | `a = a + b` | `a += 5` |
| `-=` | `a = a - b` | `a -= 5` |
| `*=` | `a = a * b` | `a *= 5` |
| `/=` | `a = a / b` | `a /= 5` |
| `%=` | `a = a % b` | `a %= 5` |

### 5.3 一元运算符

```javascript
let a = 5
console.log(a++)  // 5（后置：先使用再加 1）
console.log(a)    // 6

let b = 5
console.log(++b)  // 6（前置：先加 1 再使用）
console.log(b)    // 6
```

| 写法 | 说明 |
| --- | --- |
| `a++` | 后置自增，返回旧值 |
| `++a` | 前置自增，返回新值 |
| `a--` | 后置自减，返回旧值 |
| `--a` | 前置自减，返回新值 |

⚠️ **易错点**：`++` 在前先加再用，`++` 在后先用再加。

### 5.4 比较运算符

| 运算符 | 说明 | 示例 |
| --- | --- | --- |
| `>` | 大于 | `5 > 3` → `true` |
| `<` | 小于 | `5 < 3` → `false` |
| `>=` | 大于等于 | `5 >= 5` → `true` |
| `<=` | 小于等于 | `5 <= 3` → `false` |
| `==` | 相等（会转换） | `1 == '1'` → `true` |
| `===` | 全等（不转换） | `1 === '1'` → `false` |
| `!=` | 不等（会转换） | `1 != '1'` → `false` |
| `!==` | 不全等（不转换） | `1 !== '1'` → `true` |

### 5.5 逻辑运算符

| 运算符 | 说明 | 示例 |
| --- | --- | --- |
| `&&` | 与（全部真才真） | `true && false` → `false` |
| `\|\|` | 或（有真即为真） | `true \|\| false` → `true` |
| `!` | 非（取反） | `!true` → `false` |

**短路运算（返回值不一定是 boolean）：**

```javascript
// && 找假：遇到假就返回当前值，否则返回最后一个
console.log(0 && 1)     // 0
console.log(1 && 2)     // 2
console.log('' && 'a')  // ''
console.log(1 && 2 && 3)// 3

// || 找真：遇到真就返回当前值，否则返回最后一个
console.log(0 || 1)     // 1
console.log(1 || 2)     // 1
console.log('' || 'a')  // 'a'
console.log(null || undefined || 0) // 0

// 常用于默认值
let name = userInput || '匿名'
```

⚠️ **易错点**：逻辑运算的返回值是操作数本身（短路时返回的值），不一定是 `true`/`false`。

### 5.6 运算符优先级（从高到低）

| 优先级 | 运算符 |
| --- | --- |
| 1 | `()` 小括号 |
| 2 | 一元运算符 `++`、`--`、`!` |
| 3 | 算术运算符 `*` `/` `%` → `+` `-` |
| 4 | 关系运算符 `>` `<` `>=` `<=` |
| 5 | 相等运算符 `==` `!=` `===` `!==` |
| 6 | 逻辑运算符 `&&` → `\|\|` |
| 7 | 赋值运算符 `=` `+=` 等 |
| 8 | 逗号运算符 `,` |

⚠️ **易错点**：记不住优先级时，**用小括号 `()` 明确优先级**，提高可读性。

---

## 六、流程控制

### 6.1 if 语句

```javascript
// 单分支
if (条件) {
  // 执行代码
}

// 双分支
let age = 18
if (age >= 18) {
  console.log('成年')
} else {
  console.log('未成年')
}

// 多分支
let score = 85
if (score >= 90) {
  console.log('优秀')
} else if (score >= 80) {
  console.log('良好')
} else if (score >= 60) {
  console.log('及格')
} else {
  console.log('不及格')
}
```

⚠️ **易错点**：除 `0`、`''`、`null`、`undefined`、`NaN`、`false` 外，所有值作为条件都为真（包括 `'0'`、`'false'`、`[]`）。

### 6.2 三元运算符

```javascript
// 条件 ? 真值 : 假值
let age = 18
let result = age >= 18 ? '成年' : '未成年'
console.log(result)  // '成年'

// 嵌套（不推荐过度嵌套）
let score = 85
let level = score >= 90 ? '优秀' : score >= 60 ? '及格' : '不及格'
```

### 6.3 switch 语句

```javascript
let day = 3
switch (day) {
  case 1:
    console.log('星期一')
    break
  case 2:
    console.log('星期二')
    break
  case 3:
    console.log('星期三')
    break
  default:
    console.log('未知')
}
```

⚠️ **易错点**：
- 不写 `break` 会发生**case 穿透**（从匹配的 case 一直执行到下一个 break 或末尾）
- `switch` 比较使用的是**全等 `===`**，不会做类型转换
- `case` 后必须是具体值，不能是范围

### 6.4 if 与 switch 的区别与选择

| 对比项 | `if` | `switch` |
| --- | --- | --- |
| 条件类型 | 任意表达式（支持范围） | 等值判断（全等比较） |
| 适用场景 | 范围判断、复杂条件 | 多个固定值匹配 |
| 可读性 | 多分支稍差 | 多值匹配清晰 |

选择建议：固定值多分支用 `switch`，范围或复杂条件用 `if`。

---

## 七、循环

### 7.1 for 循环

```javascript
// for (起始值; 终止条件; 变化量) { 循环体 }
for (let i = 1; i <= 5; i++) {
  console.log(i)  // 1 2 3 4 5
}

// 求 1~100 的和
let sum = 0
for (let i = 1; i <= 100; i++) {
  sum += i
}
console.log(sum)  // 5050
```

### 7.2 while 循环

```javascript
// 不确定循环次数时使用
let i = 1
while (i <= 5) {
  console.log(i)
  i++
}
```

⚠️ **易错点**：`while` 循环体内必须有让条件最终为假的语句，否则会**死循环**。

### 7.3 do-while 循环

```javascript
// 至少执行一次
let i = 1
do {
  console.log(i)
  i++
} while (i <= 5)
```

| 循环类型 | 执行顺序 | 最少执行次数 |
| --- | --- | --- |
| `for` | 先判断后执行 | 0 次 |
| `while` | 先判断后执行 | 0 次 |
| `do-while` | 先执行后判断 | 1 次 |

### 7.4 continue 与 break

| 关键字 | 作用 |
| --- | --- |
| `continue` | 跳过本次循环，进入下一次循环 |
| `break` | 跳出整个循环 |

```javascript
// 输出 1~10 中的奇数
for (let i = 1; i <= 10; i++) {
  if (i % 2 === 0) continue  // 跳过偶数
  console.log(i)  // 1 3 5 7 9
}

// 找到第一个能被 7 整除的数
for (let i = 1; i <= 100; i++) {
  if (i % 7 === 0) {
    console.log(i)  // 7
    break           // 找到后立即跳出
  }
}
```

### 7.5 循环嵌套

```javascript
// 打印 5 行 5 列的星星
for (let i = 0; i < 5; i++) {       // 外层：行
  let row = ''
  for (let j = 0; j < 5; j++) {     // 内层：列
    row += '★ '
  }
  console.log(row)
}

// 打印九九乘法表
for (let i = 1; i <= 9; i++) {
  let row = ''
  for (let j = 1; j <= i; j++) {
    row += `${j}×${i}=${i * j}\t`
  }
  console.log(row)
}
```

⚠️ **易错点**：外层循环控制行数，内层循环控制列数；嵌套层数过多会导致性能下降。

---

## 八、数组

### 8.1 数组声明与访问

```javascript
// 字面量声明（推荐）
let arr = [10, 20, 30, 40, 50]

// new Array 声明（少用）
let arr2 = new Array(10, 20, 30)

// 访问：索引从 0 开始
console.log(arr[0])      // 10
console.log(arr[2])      // 30
console.log(arr[arr.length - 1]) // 50（最后一个元素）

// 越界访问
console.log(arr[10])     // undefined

// 数组长度
console.log(arr.length)  // 5
```

⚠️ **易错点**：JS 数组索引从 `0` 开始；越界访问返回 `undefined`（不会报错）。

### 8.2 数组遍历

```javascript
let arr = [10, 20, 30, 40]

// for 循环（最常用）
for (let i = 0; i < arr.length; i++) {
  console.log(arr[i])
}

// 求最大值
let max = arr[0]
for (let i = 1; i < arr.length; i++) {
  if (arr[i] > max) max = arr[i]
}
console.log(max)  // 40
```

### 8.3 数组操作

```javascript
let arr = ['a', 'b', 'c']

// 新增
arr.push('d')            // 末尾添加，返回新长度 4
arr.unshift('z')         // 开头添加，返回新长度 5

// 删除
arr.pop()                // 删除末尾，返回被删除的元素
arr.shift()              // 删除开头，返回被删除的元素

// 修改
arr[0] = 'A'             // 直接通过索引修改

// 查询
console.log(arr.indexOf('b'))  // 返回索引，找不到返回 -1

// 长度可写
arr.length = 2           // 截断数组
console.log(arr)         // ['A', 'b']
```

### 8.4 常用数组方法补充

| 方法 | 作用 | 是否修改原数组 |
| --- | --- | --- |
| `push(...items)` | 末尾添加 | 是 |
| `pop()` | 末尾删除 | 是 |
| `unshift(...items)` | 开头添加 | 是 |
| `shift()` | 开头删除 | 是 |
| `splice(start, deleteCount, ...items)` | 增删改 | 是 |
| `reverse()` | 反转数组 | 是 |
| `sort()` | 排序（默认按字符编码） | 是 |
| `slice(start, end)` | 截取片段 | 否，返回新数组 |
| `join(separator)` | 拼接成字符串 | 否 |
| `indexOf(item)` | 查找索引 | 否 |
| `concat(arr)` | 合并数组 | 否 |

```javascript
let arr = [3, 1, 4, 1, 5, 9, 2, 6]

// splice：增删改一体
arr.splice(2, 1)         // 从索引 2 删除 1 个 → [3,1,1,5,9,2,6]
arr.splice(1, 0, 'x')    // 从索引 1 插入 'x'
arr.splice(0, 1, 'y')    // 替换索引 0 的元素

// slice：截取（左闭右开）
let part = arr.slice(1, 3)  // 返回 [索引1, 索引3)

// join：拼接字符串
console.log([1, 2, 3].join('-'))  // '1-2-3'

// sort：默认按字符编码排序
let nums = [10, 5, 8, 1]
nums.sort()              // [1, 10, 5, 8] ⚠️ 默认按字符串比较
nums.sort((a, b) => a - b)  // [1, 5, 8, 10] 升序
nums.sort((a, b) => b - a)  // [10, 8, 5, 1] 降序

// reverse：反转
[1, 2, 3].reverse()      // [3, 2, 1]
```

⚠️ **易错点**：`sort()` 默认把元素转成字符串按字符编码排序，`10` 会排在 `2` 前面；数字排序必须传比较函数。

### 8.5 冒泡排序

**思路**：相邻元素两两比较，每轮把最大（或最小）的元素"冒泡"到末尾，共进行 `n-1` 轮。

```javascript
let arr = [5, 3, 8, 1, 9, 2]

for (let i = 0; i < arr.length - 1; i++) {        // 外层：轮数 n-1
  for (let j = 0; j < arr.length - 1 - i; j++) {  // 内层：每轮比较次数递减
    if (arr[j] > arr[j + 1]) {
      // 交换
      let temp = arr[j]
      arr[j] = arr[j + 1]
      arr[j + 1] = temp
    }
  }
}
console.log(arr)  // [1, 2, 3, 5, 8, 9]
```

⚠️ **易错点**：
- 外层循环次数是 `n - 1`
- 内层循环次数是 `n - 1 - i`（每轮结束后最大值已就位，无需再比较）
- 交换借助第三个变量 `temp`

---

## 九、函数

### 9.1 函数声明与调用

```javascript
// 声明
function sayHi() {
  console.log('Hello')
}

// 调用
sayHi()
```

⚠️ **易错点**：函数只声明不调用不会执行；函数名加 `()` 是调用，不加 `()` 是引用函数本身。

### 9.2 参数

```javascript
// 形参：声明时的占位符；实参：调用时传入的值
function add(x, y) {     // x、y 是形参
  return x + y
}
add(3, 5)                // 3、5 是实参

// 默认参数（ES6）
function greet(name = '匿名') {
  console.log(`Hello, ${name}`)
}
greet()        // 'Hello, 匿名'
greet('张三')  // 'Hello, 张三'
```

**形参实参个数不匹配：**

| 情况 | 结果 |
| --- | --- |
| 实参 < 形参 | 多余形参为 `undefined` |
| 实参 > 形参 | 多余实参被忽略（但仍可通过 `arguments` 访问） |

### 9.3 返回值 return

```javascript
function getMax(a, b) {
  return a > b ? a : b   // return 将结果返回给调用者
}
let max = getMax(3, 5)
console.log(max)  // 5

// 无 return 或 return 后无值，返回 undefined
function fn() {}
console.log(fn())  // undefined
```

⚠️ **易错点**：
- `return` 后的代码不会执行
- `return` 只能返回一个值，多个值用数组或对象包裹
- 函数没有 `return` 时默认返回 `undefined`

### 9.4 匿名函数与函数表达式

```javascript
// 函数声明（有名字）
function fn1() {
  console.log('fn1')
}

// 函数表达式（匿名函数赋值给变量）
let fn2 = function () {
  console.log('fn2')
}
fn2()

// 立即执行函数 IIFE
;(function () {
  console.log('自动执行')
})()
```

⚠️ **易错点**：函数声明有**提升**（可在声明前调用），函数表达式**不会提升**（必须先赋值后调用）。

### 9.5 箭头函数基础（ES6）

```javascript
// 完整写法
const add = (a, b) => {
  return a + b
}

// 简写：只有一个参数可省略 ()
const fn = x => {
  return x * 2
}

// 简写：函数体只有一句 return，可省略 {} 和 return
const double = x => x * 2

// 无参数
const sayHi = () => console.log('hi')
```

⚠️ **易错点**：箭头函数没有自己的 `this`、`arguments`，不能作为构造函数，不能使用 `new`。

### 9.6 arguments 与剩余参数

```javascript
// arguments：函数内部可用的伪数组，包含所有实参
function sum() {
  let total = 0
  for (let i = 0; i < arguments.length; i++) {
    total += arguments[i]
  }
  return total
}
sum(1, 2, 3)  // 6

// 剩余参数（ES6，推荐）
function sum2(...nums) {
  return nums.reduce((a, b) => a + b, 0)
}
sum2(1, 2, 3, 4)  // 10
```

⚠️ **易错点**：`arguments` 是伪数组（有 length 和索引，但没有数组方法如 `push`、`forEach`）；箭头函数中没有 `arguments`，需用剩余参数。

---

## 十、作用域

### 10.1 全局作用域

```javascript
// 写在 script 标签或 .js 文件最外层的变量
let globalVar = '我是全局变量'

function fn() {
  console.log(globalVar)  // 函数内可访问
}
```

### 10.2 局部/函数作用域

```javascript
function fn() {
  let localVar = '我是局部变量'
}
console.log(localVar)  // ReferenceError（函数外无法访问）
```

### 10.3 块级作用域

```javascript
{
  let a = 1
  const b = 2
  var c = 3
}
console.log(a)  // ReferenceError（let 块级作用域）
console.log(b)  // ReferenceError（const 块级作用域）
console.log(c)  // 3 ⚠️ var 无块级作用域，泄漏到外部
```

### 10.4 作用域链

```javascript
let a = 1
function outer() {
  let b = 2
  function inner() {
    let c = 3
    console.log(a, b, c)  // 1 2 3，逐层向外查找
  }
  inner()
}
outer()
```

**作用域链**：内部函数访问变量时，先在自身作用域查找，找不到就一层层向外查找，直到全局作用域。

### 10.5 变量提升

```javascript
console.log(x)  // undefined（var 声明被提升，赋值不提升）
var x = 10

// 等价于：
var x
console.log(x)
x = 10

// let/const 不会提升（暂时性死区 TDZ）
console.log(y)  // ReferenceError
let y = 20
```

⚠️ **易错点**：`var` 声明被提升，但赋值不提升；`let`/`const` 存在暂时性死区（TDZ），声明前访问直接报错。

---

## 十一、对象

### 11.1 对象声明（字面量）

```javascript
let obj = {
  name: '张三',
  age: 18,
  isStudent: true,
  hobbies: ['读书', '游戏'],
  sayHi: function () {
    console.log('Hi, I am ' + this.name)
  }
}
```

### 11.2 属性与方法

```javascript
// 属性：对象中的变量
// 方法：对象中的函数
let user = {
  name: '李四',              // 属性
  greet: function () {       // 方法
    console.log('Hello, ' + this.name)
  }
}
user.greet()  // 'Hello, 李四'
```

### 11.3 属性访问

```javascript
let obj = { name: '张三', 'age-2': 18 }

// . 语法（属性名是合法标识符时使用）
console.log(obj.name)  // '张三'

// [] 语法（属性名包含特殊字符或为变量时使用）
console.log(obj['name'])       // '张三'
console.log(obj['age-2'])      // 18（特殊字符属性只能用 []）

let key = 'name'
console.log(obj[key])          // '张三'（变量名做 key）
```

⚠️ **易错点**：属性名含 `-`、空格等特殊字符时必须用 `[]` 访问；用变量做属性名时也只能用 `[]`。

### 11.4 遍历对象

```javascript
let obj = { name: '张三', age: 18, gender: '男' }

// for...in 遍历对象
for (let key in obj) {
  console.log(key, obj[key])   // name 张三 / age 18 / gender 男
}
```

⚠️ **易错点**：`for...in` 中要用 `obj[key]` 而不是 `obj.key`（`key` 是变量）。

### 11.5 Math 内置对象

| 方法/属性 | 作用 | 示例 |
| --- | --- | --- |
| `Math.PI` | 圆周率 | `3.141592653589793` |
| `Math.max(a, b, ...)` | 最大值 | `Math.max(1, 3, 2)` → `3` |
| `Math.min(a, b, ...)` | 最小值 | `Math.min(1, 3, 2)` → `1` |
| `Math.abs(x)` | 绝对值 | `Math.abs(-5)` → `5` |
| `Math.floor(x)` | 向下取整 | `Math.floor(3.9)` → `3` |
| `Math.ceil(x)` | 向上取整 | `Math.ceil(3.1)` → `4` |
| `Math.round(x)` | 四舍五入 | `Math.round(3.5)` → `4` |
| `Math.random()` | 0~1 之间随机小数（含 0 不含 1） | `0.456...` |
| `Math.pow(x, y)` | x 的 y 次幂 | `Math.pow(2, 3)` → `8` |

```javascript
console.log(Math.max(1, 2, 3))        // 3
console.log(Math.max(...[1, 2, 3]))   // 3（配合展开运算符）
console.log(Math.floor(3.9))          // 3
console.log(Math.round(3.4))          // 3
console.log(Math.round(3.5))          // 4
console.log(Math.round(-3.5))         // -3 ⚠️ 注意负数
```

⚠️ **易错点**：`Math.max()` 传入数组会得到 `NaN`，需用展开运算符 `...arr`；`Math.round` 对 `.5` 的处理是向正无穷方向取整。

### 11.6 随机数函数封装

```javascript
// 生成 [0, 1) 的随机小数
Math.random()

// 生成 [0, N) 的随机整数
function getRandomInt(N) {
  return Math.floor(Math.random() * N)
}

// 生成 [min, max] 的随机整数（包含两端）
function getRandom(min, max) {
  return Math.floor(Math.random() * (max - min + 1)) + min
}

// 示例：生成 1~10 的随机数
console.log(getRandom(1, 10))

// 示例：从数组中随机取一个元素
let arr = ['苹果', '香蕉', '橘子', '葡萄']
let randomItem = arr[Math.floor(Math.random() * arr.length)]
```

⚠️ **易错点**：生成 `[min, max]` 区间整数公式：`Math.floor(Math.random() * (max - min + 1)) + min`，别忘 `+1` 才能取到 `max`。

---

## 十二、数据存储

### 12.1 基本类型存储

**基本类型（number、string、boolean、undefined、null）存储在栈中，赋值时是值传递（拷贝一份）。**

```javascript
let a = 10
let b = a   // 拷贝值
b = 20
console.log(a)  // 10（a 不受影响）
```

### 12.2 引用类型存储

**引用类型（object、array、function）存储在堆中，变量保存的是堆内存的地址（引用），赋值时是引用传递（共享同一地址）。**

```javascript
let obj1 = { name: '张三' }
let obj2 = obj1   // 拷贝地址，指向同一对象
obj2.name = '李四'
console.log(obj1.name)  // '李四' ⚠️ obj1 也变了

let arr1 = [1, 2, 3]
let arr2 = arr1
arr2.push(4)
console.log(arr1)  // [1, 2, 3, 4]（同一个数组）
```

| 对比项 | 基本类型 | 引用类型 |
| --- | --- | --- |
| 存储位置 | 栈 | 堆（变量在栈存地址） |
| 赋值方式 | 值传递（拷贝） | 引用传递（共享地址） |
| 比较方式 | 按值比较 | 按地址比较 |
| 示例 | `1 === 1` → `true` | `{} === {}` → `false` |

⚠️ **易错点**：两个看起来一样的对象/数组用 `===` 比较是 `false`，因为比较的是地址而非内容。

---

## 💡 关联面试题

**Q1：let、var、const 三者的区别？**

| 对比项 | `var` | `let` | `const` |
| --- | --- | --- | --- |
| 作用域 | 函数作用域 | 块级作用域 | 块级作用域 |
| 变量提升 | 是（值为 undefined） | 暂时性死区 | 暂时性死区 |
| 重复声明 | 允许 | 不允许 | 不允许 |
| 重新赋值 | 允许 | 允许 | 不允许 |
| 必须初始化 | 否 | 否 | 是 |
| 挂载到 window | 是 | 否 | 否 |

实际开发中：默认用 `const`，需要重新赋值用 `let`，避免使用 `var`。

**Q2：== 和 === 的区别？**
- `==`（相等）：比较前会做隐式类型转换，如 `1 == '1'` → `true`、`null == undefined` → `true`
- `===`（全等）：不转换类型，类型和值都必须相等，如 `1 === '1'` → `false`
- 实际开发**始终使用 `===`**，避免隐式转换导致的 bug

**Q3：typeof 能判断哪些类型？**
- 能准确判断：`number`、`string`、`boolean`、`undefined`、`function`、`symbol`、`bigint`
- 判断对象：`typeof {}` → `'object'`，`typeof []` → `'object'`，`typeof null` → `'object'`（历史 bug）
- 无法区分数组、对象、null，需配合 `Array.isArray()`、`instanceof`、`Object.prototype.toString.call()`

**Q4：什么是变量提升？**
- JS 引擎在执行代码前会先扫描作用域，把 `var` 声明和 `function` 声明**提升到作用域顶部**
- `var` 声明提升但赋值不提升，访问得到 `undefined`
- `function` 整体提升（声明 + 函数体）
- `let`/`const` 存在暂时性死区（TDZ），声明前访问会报 `ReferenceError`
- 建议：先声明再使用，避免依赖变量提升

**Q5：基本数据类型和引用数据类型在存储上的区别？**
- **基本类型**（number、string、boolean、undefined、null、symbol、bigint）：存储在**栈**中，赋值是值拷贝，互不影响
- **引用类型**（object、array、function）：内容存储在**堆**中，变量在栈中保存堆地址，赋值是地址拷贝，多个变量指向同一对象，修改互相影响
- 比较时基本类型按值比较，引用类型按地址比较（`{} === {}` 为 `false`）

**Q6：冒泡排序的思路？**
- 相邻元素两两比较，前一个比后一个大就交换
- 每轮结束后，当前未排序部分的最大值"冒泡"到末尾
- 共进行 `n - 1` 轮，第 `i` 轮比较 `n - 1 - i` 次
- 时间复杂度 O(n²)，空间复杂度 O(1)，是稳定排序

```javascript
for (let i = 0; i < arr.length - 1; i++) {
  for (let j = 0; j < arr.length - 1 - i; j++) {
    if (arr[j] > arr[j + 1]) {
      [arr[j], arr[j + 1]] = [arr[j + 1], arr[j]]
    }
  }
}
```

**Q7：for...in 和 for...of 的区别？**

| 对比项 | `for...in` | `for...of` |
| --- | --- | --- |
| 遍历目标 | 对象的**键**（key） | 可迭代对象的**值**（value） |
| 适用对象 | 对象、数组（不推荐） | 数组、字符串、Map、Set 等**可迭代对象** |
| 数组遍历得到 | 索引（字符串形式） | 元素值 |
| 能否遍历对象 | ✅ 可以 | ❌ 普通对象不可迭代 |
| 原型链 | 会遍历原型链上的属性 | 不会 |

```javascript
let arr = [10, 20, 30]
for (let i in arr) console.log(i)      // '0' '1' '2'（字符串索引）
for (let v of arr) console.log(v)      // 10 20 30（值）

let obj = { a: 1, b: 2 }
for (let k in obj) console.log(k)      // 'a' 'b'
// for (let v of obj) ...              // TypeError（对象不可迭代）
```

总结：**遍历对象用 `for...in`，遍历数组用 `for...of`**。
