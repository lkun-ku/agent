# TypeScript 复习

> TypeScript 是 JavaScript 的超集，为 JS 添加了静态类型系统，使代码更健壮、更易维护，是大型项目开发的首选。

## 一、TypeScript 简介

### 1.1 什么是 TypeScript

- JS 的超集，添加了类型系统
- 编译时类型检查，运行时还是 JS
- 优势：更早发现错误、代码提示更好、重构更安全、团队协作更友好

### 1.2 安装与使用

```bash
# 全局安装
npm i -g typescript

# 初始化配置文件
tsc --init

# 编译 ts → js
tsc index.ts

# 直接运行 ts（需安装 ts-node）
npm i -g ts-node
ts-node index.ts
```

### 1.3 tsconfig.json 常用配置

| 配置项 | 说明 |
| --- | --- |
| `target` | 编译目标 ES 版本（如 `ES2015`、`ESNext`） |
| `strict` | 开启所有严格类型检查（推荐 `true`） |
| `module` | 模块系统（`commonjs`、`esnext`） |
| `outDir` | 编译输出目录 |
| `rootDir` | 源代码根目录 |
| `noImplicitAny` | 禁止隐式 any |
| `strictNullChecks` | 严格 null 检查 |

```json
{
  "compilerOptions": {
    "target": "ES2015",
    "module": "commonjs",
    "strict": true,
    "outDir": "./dist",
    "rootDir": "./src",
    "esModuleInterop": true,
    "skipLibCheck": true
  }
}
```

> ⚠️ **易错点**：`strict: true` 会同时开启 `strictNullChecks`、`noImplicitAny` 等多个严格选项，建议项目始终开启。

---

## 二、基础类型

### 2.1 基本类型

```typescript
let str: string = 'hello'
let num: number = 100
let isDone: boolean = true
let n: null = null
let u: undefined = undefined
let sym: symbol = Symbol('id')
let big: bigint = 100n
```

### 2.2 数组类型

```typescript
// 两种写法等价
let arr1: number[] = [1, 2, 3]
let arr2: Array<number> = [1, 2, 3]

// 混合类型数组
let arr3: (number | string)[] = [1, 'a', 2]
```

### 2.3 元组 Tuple

> 固定长度和类型的数组，已知每个位置的类型。

```typescript
let tuple: [string, number] = ['lkun', 18]

// 访问
console.log(tuple[0]) // 'lkun'

// ⚠️ 越界访问会报错
tuple[2] = 'x' // 报错
```

| 对比 | 数组 | 元组 |
| --- | --- | --- |
| 长度 | 不固定 | 固定 |
| 类型 | 同一类型 | 每位可不同 |
| 写法 | `number[]` | `[string, number]` |

### 2.4 枚举 Enum

```typescript
// 1. 数字枚举（默认从 0 开始，可手动指定）
enum Direction {
  Up = 0,
  Down,   // 1
  Left,   // 2
  Right   // 3
}
let d: Direction = Direction.Up

// 2. 字符串枚举
enum Color {
  Red = 'RED',
  Green = 'GREEN',
  Blue = 'BLUE'
}

// 3. 异构枚举（不推荐）
enum BooleanLikeHeterogeneousEnum {
  No = 0,
  Yes = 'YES'
}

// 4. const enum（编译时内联，不生成对象）
const enum E {
  A,
  B
}
let e = E.A // 编译后直接变成 let e = 0
```

> ⚠️ **易错点**：数字枚举会生成正向（名→值）和反向（值→名）映射，字符串枚举只有正向映射。

### 2.5 any 与 unknown

```typescript
// any：放弃类型检查，可任意操作
let a: any = 1
a = 'string'
a.foo() // 不报错（运行时可能出错）

// unknown：安全的 any，使用前必须类型收窄
let b: unknown = 'hello'
// b.toUpperCase() // ❌ 报错：Object is of type 'unknown'

if (typeof b === 'string') {
  console.log(b.toUpperCase()) // ✅ 类型收窄后可用
}
```

| 对比 | any | unknown |
| --- | --- | --- |
| 类型检查 | 关闭 | 开启 |
| 任意赋值 | ✅ | ✅ |
| 任意读取属性/调用 | ✅ | ❌（必须先收窄） |
| 推荐度 | ❌ 避免 | ✅ 推荐 |

> 💡 **重点**：优先使用 `unknown` 替代 `any`，强制进行类型检查，更安全。

### 2.6 void、never、object

```typescript
// void：函数无返回值
function log(msg: string): void {
  console.log(msg)
}

// never：永远不会有值（抛异常、无限循环、永远为假的判断）
function error(msg: string): never {
  throw new Error(msg)
}

function infiniteLoop(): never {
  while (true) {}
}

// object：非原始类型
let obj: object = { name: 'lkun' }
let arr: object = [1, 2, 3]
```

> ⚠️ **易错点**：`object` 类型太宽泛，一般用具体对象类型或 `Record<string, unknown>` 代替。

### 2.7 类型推断

```typescript
// 变量声明时自动推断
let x = 10       // 推断为 number
let s = 'hello'  // 推断为 string

// 函数返回值自动推断
function add(a: number, b: number) {
  return a + b   // 返回值推断为 number
}
```

---

## 三、类型断言与类型守卫

### 3.1 类型断言

```typescript
// 方式一：as 语法（推荐，JSX 中唯一可用）
let someValue: unknown = 'this is a string'
let strLength: number = (someValue as string).length

// 方式二：尖括号语法（JSX 中不可用）
let strLength2: number = (<string>someValue).length
```

> ⚠️ **易错点**：类型断言会绕过编译检查，若断言错误运行时会报错，应配合类型守卫使用。

### 3.2 类型守卫

```typescript
// 1. typeof：判断基本类型
function padLeft(value: string | number) {
  if (typeof value === 'number') {
    return ' '.repeat(value) // 这里 value 是 number
  }
  return value // 这里 value 是 string
}

// 2. instanceof：判断实例
class Cat { meow() {} }
class Dog { bark() {} }
function speak(pet: Cat | Dog) {
  if (pet instanceof Cat) {
    pet.meow()
  } else {
    pet.bark()
  }
}

// 3. in：判断属性是否存在
interface Fish { swim(): void }
interface Bird { fly(): void }
function move(animal: Fish | Bird) {
  if ('swim' in animal) {
    animal.swim()
  } else {
    animal.fly()
  }
}

// 4. 自定义类型谓词：value is Type
function isString(x: unknown): x is string {
  return typeof x === 'string'
}
function handle(x: unknown) {
  if (isString(x)) {
    x.toUpperCase() // x 被收窄为 string
  }
}
```

| 类型守卫 | 适用场景 | 示例 |
| --- | --- | --- |
| `typeof` | 基本类型 | `typeof x === 'string'` |
| `instanceof` | 类实例 | `pet instanceof Cat` |
| `in` | 对象属性 | `'swim' in animal` |
| `is` 谓词 | 复杂判断 | `x is string` |

---

## 四、接口 Interface

### 4.1 基本用法

```typescript
interface Person {
  name: string
  age: number
  readonly id: number   // 只读属性
  gender?: string       // 可选属性
}

const p: Person = {
  id: 1,
  name: 'lkun',
  age: 18
}
// p.id = 2  // ❌ 只读属性不可修改
```

### 4.2 函数类型接口

```typescript
interface SearchFunc {
  (source: string, subString: string): boolean
}

const mySearch: SearchFunc = (src, sub) => {
  return src.search(sub) > -1
}
```

### 4.3 可索引接口

```typescript
interface StringArray {
  [index: number]: string
}

const arr: StringArray = ['a', 'b', 'c']

interface ObjMap {
  [key: string]: string
}

const obj: ObjMap = { name: 'lkun', city: 'beijing' }
```

### 4.4 接口继承 extends

```typescript
interface Animal {
  name: string
}

interface Dog extends Animal {
  bark(): void
}

const dog: Dog = {
  name: '旺财',
  bark() { console.log('汪汪') }
}
```

### 4.5 interface 与 type 的区别

| 对比项 | interface | type |
| --- | --- | --- |
| 对象描述 | ✅ 支持 | ✅ 支持 |
| 联合类型 | ❌ 不支持 | ✅ 支持 |
| 交叉类型 | ❌ 不支持 | ✅ 支持 |
| 原始类型别名 | ❌ 不支持 | ✅ 支持 |
| 声明合并 | ✅ 支持 | ❌ 不支持 |
| 继承 | `extends` | `&` |
| 扩展自身 | 可重复定义合并 | 不可重复 |

```typescript
// interface 声明合并
interface Window {
  myProp: string
}
interface Window {
  otherProp: number
}
// 合并为 Window { myProp: string; otherProp: number }

// type 联合类型（interface 做不到）
type Status = 'success' | 'error' | 'loading'
```

> 💡 **重点**：定义对象形状优先用 `interface`（支持声明合并、可扩展）；需要联合/交叉/原始别名时用 `type`。

---

## 五、类型别名 type

### 5.1 基本用法

```typescript
type Name = string
type NameResolver = () => string
type NameOrResolver = Name | NameResolver

function getName(n: NameOrResolver): Name {
  if (typeof n === 'string') return n
  return n()
}
```

### 5.2 联合类型 |

```typescript
type ID = number | string

function printId(id: ID) {
  console.log(id)
}

// 字面量联合类型
type Direction = 'up' | 'down' | 'left' | 'right'
```

### 5.3 交叉类型 &

```typescript
interface Person { name: string }
interface Loggable { log(): void }

type PersonLogger = Person & Loggable

const pl: PersonLogger = {
  name: 'lkun',
  log() { console.log(this.name) }
}
```

### 5.4 工具类型（内置）

```typescript
interface User {
  id: number
  name: string
  age: number
  email: string
}

// Partial<T>：所有属性可选
type PartialUser = Partial<User>
// { id?: number; name?: string; age?: number; email?: string }

// Required<T>：所有属性必填
type RequiredUser = Required<PartialUser>

// Pick<T, K>：选取部分属性
type UserBasic = Pick<User, 'id' | 'name'>
// { id: number; name: string }

// Omit<T, K>：排除部分属性
type UserWithoutId = Omit<User, 'id' | 'email'>
// { name: string; age: number }

// Record<K, T>：键值对
type UserMap = Record<string, User>
const users: UserMap = {
  u1: { id: 1, name: 'a', age: 18, email: 'a@x.com' }
}

// ReturnType<T>：获取函数返回值类型
function fn() { return { x: 1, y: 2 } }
type FnResult = ReturnType<typeof fn>  // { x: number; y: number }

// Parameters<T>：获取函数参数类型（元组）
type FnParams = Parameters<typeof fn>   // []
```

| 工具类型 | 作用 |
| --- | --- |
| `Partial<T>` | 所有属性变可选 |
| `Required<T>` | 所有属性变必填 |
| `Readonly<T>` | 所有属性变只读 |
| `Pick<T, K>` | 选取部分属性 |
| `Omit<T, K>` | 排除部分属性 |
| `Record<K, T>` | 构造键值对类型 |
| `ReturnType<T>` | 获取函数返回值类型 |
| `Parameters<T>` | 获取函数参数元组类型 |
| `Exclude<T, U>` | 从联合类型中排除 |
| `Extract<T, U>` | 从联合类型中提取 |

---

## 六、泛型（重点）

### 6.1 泛型函数

```typescript
// 不预先指定类型，使用时再传入
function identity<T>(arg: T): T {
  return arg
}

// 调用方式一：显式指定
let out1 = identity<string>('hello')

// 调用方式二：类型推断（推荐）
let out2 = identity(123) // T 推断为 number
```

> 💡 **重点**：泛型本质是「类型的参数化」，让组件可以复用多种类型，同时保持类型安全。

### 6.2 泛型接口

```typescript
interface GenericIdentityFn<T> {
  (arg: T): T
}

const myIdentity: GenericIdentityFn<number> = (arg) => arg
console.log(myIdentity(100))
```

### 6.3 泛型类

```typescript
class GenericNumber<T> {
  zeroValue: T
  add: (x: T, y: T) => T
  constructor(zeroValue: T, addFn: (x: T, y: T) => T) {
    this.zeroValue = zeroValue
    this.add = addFn
  }
}

const numUtil = new GenericNumber<number>(0, (x, y) => x + y)
console.log(numUtil.add(1, 2)) // 3
```

### 6.4 泛型约束 extends

```typescript
// 限制泛型必须包含某些属性
interface Lengthwise {
  length: number
}

function loggingIdentity<T extends Lengthwise>(arg: T): T {
  console.log(arg.length) // 保证有 length 属性
  return arg
}

loggingIdentity([1, 2, 3])    // ✅
loggingIdentity('hello')      // ✅
// loggingIdentity(123)       // ❌ number 没有 length
```

### 6.5 多个泛型参数

```typescript
function swap<T, U>(tuple: [T, U]): [U, T] {
  return [tuple[1], tuple[0]]
}

const result = swap<string, number>('a', 1) // [1, 'a']
```

### 6.6 默认泛型类型

```typescript
function fn<T = string>(arg: T): T {
  return arg
}

const s = fn()      // T 默认为 string
const n = fn(123)   // T 推断为 number
```

> ⚠️ **易错点**：泛型约束 `extends` 用法：
> - `T extends SomeType` 表示 T 必须满足 SomeType（约束）
> - 与类继承的 `extends` 语法一致但语义不同

---

## 七、函数类型

### 7.1 函数声明类型

```typescript
// 参数类型 + 返回值类型
function add(a: number, b: number): number {
  return a + b
}

// 完整函数类型定义
const myAdd: (x: number, y: number) => number = function (x, y) {
  return x + y
}
```

### 7.2 可选参数与默认参数

```typescript
// 可选参数（必须在必填参数后）
function buildName(firstName: string, lastName?: string) {
  return lastName ? `${firstName} ${lastName}` : firstName
}

// 默认参数
function greet(name: string = 'Guest') {
  return `Hello, ${name}`
}
```

> ⚠️ **易错点**：可选参数 `?` 必须放在必填参数后面；默认参数会自动推断为可选。

### 7.3 剩余参数

```typescript
function sum(...nums: number[]): number {
  return nums.reduce((acc, cur) => acc + cur, 0)
}
console.log(sum(1, 2, 3, 4)) // 10
```

### 7.4 函数重载

```typescript
// 多个函数签名 + 一个实现
function overload(x: number): number
function overload(x: string): string
function overload(x: number | string): number | string {
  if (typeof x === 'number') return x * 2
  return x.repeat(2)
}

console.log(overload(3))      // 6
console.log(overload('ab'))   // 'abab'
```

> 💡 **重点**：重载签名不包含实现，TS 会根据调用时的实参类型匹配最合适的重载版本。

---

## 八、类

### 8.1 类的类型注解

```typescript
class Person {
  name: string        // 属性类型
  age: number

  constructor(name: string, age: number) {
    this.name = name
    this.age = age
  }

  sayHi(): void {
    console.log(`Hi, I'm ${this.name}`)
  }
}

const p = new Person('lkun', 18)
```

### 8.2 访问修饰符

```typescript
class Animal {
  public name: string        // 公开（默认）
  private id: number         // 私有，仅类内可访问
  protected species: string  // 受保护，类内和子类可访问

  constructor(name: string, id: number, species: string) {
    this.name = name
    this.id = id
    this.species = species
  }
}

class Dog extends Animal {
  bark() {
    // this.id  // ❌ private 不可访问
    console.log(`${this.species} ${this.name} is barking`) // ✅
  }
}
```

| 修饰符 | 类内 | 子类 | 类外 |
| --- | --- | --- | --- |
| `public` | ✅ | ✅ | ✅ |
| `protected` | ✅ | ✅ | ❌ |
| `private` | ✅ | ❌ | ❌ |

### 8.3 readonly 修饰符

```typescript
class Person {
  readonly id: number
  constructor(id: number) {
    this.id = id
  }
}
const p = new Person(1)
// p.id = 2  // ❌ 只读属性不可修改
```

### 8.4 参数属性（构造函数参数简写）

```typescript
// 等价于声明属性 + 构造函数赋值
class Person {
  constructor(
    public name: string,
    private age: number,
    readonly id: number
  ) {}
}

const p = new Person('lkun', 18, 1)
console.log(p.name) // 'lkun'
```

### 8.5 存储器 getter/setter

```typescript
class Employee {
  private _salary: number = 0

  get salary(): number {
    return this._salary
  }

  set salary(value: number) {
    if (value < 0) throw new Error('工资不能为负数')
    this._salary = value
  }
}

const emp = new Employee()
emp.salary = 10000
console.log(emp.salary) // 10000
```

### 8.6 抽象类 abstract

```typescript
abstract class Animal {
  abstract makeSound(): void  // 抽象方法，子类必须实现
  move(): void {
    console.log('移动中...')
  }
}

class Cat extends Animal {
  makeSound(): void {
    console.log('喵')
  }
}

// const a = new Animal()  // ❌ 抽象类不能实例化
const cat = new Cat()
cat.makeSound() // '喵'
cat.move()      // '移动中...'
```

### 8.7 类与接口实现 implements

```typescript
interface ClockInterface {
  currentTime: Date
  setTime(d: Date): void
}

class Clock implements ClockInterface {
  currentTime: Date = new Date()
  setTime(d: Date) {
    this.currentTime = d
  }
}
```

> ⚠️ **易错点**：`implements` 只检查类的实例部分，不检查静态部分；一个类可实现多个接口（逗号分隔）。

---

## 九、类型声明文件

### 9.1 什么是 .d.ts 文件

> 类型声明文件（declaration file），只包含类型信息，不包含实现，用于为 JS 代码提供类型支持。

```typescript
// math.d.ts
declare function add(a: number, b: number): number
declare const version: string

declare namespace MyLib {
  function greet(name: string): string
}
```

### 9.2 内置类型声明（@types/xxx）

```bash
# 安装第三方库的类型声明
npm i -D @types/lodash
npm i -D @types/node
```

> 💡 **重点**：可通过 [TypeSearch](https://www.typescriptlang.org/dt/search) 查找第三方库对应的 `@types` 包。

### 9.3 自定义类型声明文件

```typescript
// global.d.ts - 全局声明
declare interface Window {
  myGlobalVar: string
}

// modules.d.ts - 模块声明
declare module '*.png' {
  const value: string
  export default value
}

declare module 'my-unknown-lib' {
  export function doSomething(x: string): void
}
```

### 9.4 三斜线指令

```typescript
/// <reference types="node" />
/// <reference path="./other.d.ts" />

// 用于显式声明文件之间的依赖
```

> ⚠️ **易错点**：现代项目中三斜线指令已较少使用，推荐在 `tsconfig.json` 的 `types` 和 `include` 中配置。

---

## 十、TS + React 实战

### 10.1 React 组件类型

```typescript
import React from 'react'

// 方式一：React.FC（带 children 类型）
const Greeting: React.FC<{ name: string }> = ({ name }) => {
  return <h1>Hello, {name}</h1>
}

// 方式二：直接定义 props 类型（推荐，更简洁）
interface ButtonProps {
  text: string
  onClick: () => void
  disabled?: boolean
}

function Button({ text, onClick, disabled }: ButtonProps) {
  return (
    <button onClick={onClick} disabled={disabled}>
      {text}
    </button>
  )
}
```

> 💡 **重点**：`React.FC` 会自动包含 `children`，但在新版本中已不再隐式包含，推荐直接用 props 接口定义。

### 10.2 useState 类型

```typescript
import { useState } from 'react'

// 类型推断
const [count, setCount] = useState(0)              // number
const [name, setName] = useState('lkun')           // string

// 显式指定（推荐用于复杂类型）
const [list, setList] = useState<string[]>([])
const [user, setUser] = useState<{ name: string; age: number } | null>(null)

// 惰性初始化
const [data, setData] = useState<number>(() => {
  return expensiveComputation()
})
```

### 10.3 事件类型

```typescript
import React, { useState } from 'react'

function Form() {
  const [value, setValue] = useState('')

  // React.ChangeEvent<HTMLInputElement> - input 变化事件
  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setValue(e.target.value)
  }

  // React.MouseEvent<HTMLButtonElement> - 鼠标点击事件
  const handleClick = (e: React.MouseEvent<HTMLButtonElement>) => {
    console.log('点击坐标', e.clientX, e.clientY)
  }

  // React.KeyboardEvent - 键盘事件
  const handleKey = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') console.log('回车')
  }

  return (
    <>
      <input value={value} onChange={handleChange} onKeyDown={handleKey} />
      <button onClick={handleClick}>提交</button>
    </>
  )
}
```

| 常用事件类型 | 适用元素 |
| --- | --- |
| `React.ChangeEvent<HTMLInputElement>` | input、textarea、select |
| `React.MouseEvent<HTMLButtonElement>` | 鼠标点击 |
| `React.KeyboardEvent<HTMLInputElement>` | 键盘事件 |
| `React.FormEvent<HTMLFormElement>` | 表单提交 |

### 10.4 组件通信类型化

```typescript
// 父传子：props 类型
interface TodoItemProps {
  id: number
  text: string
  done: boolean
  onToggle: (id: number) => void
  onDelete: (id: number) => void
}

function TodoItem({ id, text, done, onToggle, onDelete }: TodoItemProps) {
  return (
    <li>
      <input
        type="checkbox"
        checked={done}
        onChange={() => onToggle(id)}
      />
      <span style={{ textDecoration: done ? 'line-through' : 'none' }}>
        {text}
      </span>
      <button onClick={() => onDelete(id)}>删除</button>
    </li>
  )
}

// 子传父：通过回调函数类型
function TodoList() {
  const [todos, setTodos] = useState<TodoItemProps[]>([])

  const handleToggle = (id: number) => {
    setTodos(todos.map(t => t.id === id ? { ...t, done: !t.done } : t))
  }

  const handleDelete = (id: number) => {
    setTodos(todos.filter(t => t.id !== id))
  }

  return (
    <ul>
      {todos.map(todo => (
        <TodoItem
          key={todo.id}
          {...todo}
          onToggle={handleToggle}
          onDelete={handleDelete}
        />
      ))}
    </ul>
  )
}
```

### 10.5 类型声明文件共享类型（.d.ts）

```typescript
// types/todo.d.ts - 共享类型定义
export interface Todo {
  id: number
  text: string
  done: boolean
}

// 在组件中使用
import { Todo } from '../types/todo'

function TodoList() {
  const [todos, setTodos] = useState<Todo[]>([])
  // ...
}
```

> ⚠️ **易错点**：
> - 公共类型建议放 `types/` 目录统一管理，避免循环引用
> - `useState` 泛型一定要写全，例如 `useState<Todo[]>([])` 而非 `useState([])`
> - 事件处理函数若不传参，可用 `React.MouseEventHandler<HTMLButtonElement>` 作为类型

---

## 💡 关联面试题

**Q1：TypeScript 和 JavaScript 的区别？**
- TS 是 JS 的超集，添加了静态类型系统
- JS 是动态类型，运行时才暴露错误；TS 是静态类型，编译时就能发现错误
- TS 代码需编译为 JS 才能运行，但提供更好的代码提示、重构安全性和团队协作体验

**Q2：interface 和 type 有什么区别？**
- `interface` 只能描述对象/函数形状，支持声明合并、`extends` 继承
- `type` 可以表示联合、交叉、原始别名等任意类型，但不能声明合并
- 描述对象形状优先用 `interface`，需要联合/交叉类型时用 `type`

**Q3：any 和 unknown 的区别？**
- `any` 关闭类型检查，可任意读写属性和方法，相当于放弃 TS 的类型保护
- `unknown` 是「安全的 any」，可以接收任意值，但使用前必须经过类型收窄（typeof、instanceof、类型断言）
- 实际开发优先用 `unknown`，强制做类型检查，避免 `any` 的隐患

**Q4：什么是泛型？泛型的作用？**
- 泛型是「类型的参数化」，不预先指定具体类型，使用时再传入
- 作用：让函数、接口、类可以复用多种类型，同时保持类型安全（不同于 any）
- 通过 `T`、`U` 等类型变量表示，可用 `extends` 进行约束

**Q5：enum 的实现原理？**
- 数字枚举编译后生成一个对象，同时具有正向映射（名→值）和反向映射（值→名）
- 字符串枚举只有正向映射，不生成反向映射
- `const enum` 在编译时被内联，不生成任何对象，体积更小

**Q6：type 和 interface 什么时候用哪个？**
- 描述对象、类的形状，或需要扩展/声明合并 → 用 `interface`
- 需要联合类型、交叉类型、原始类型别名、元组、字面量类型 → 用 `type`
- React 组件 props 一般用 `interface`（更易扩展和实现）

**Q7：TS 的类型断言和类型守卫有什么区别？**
- 类型断言（`as`）是「告诉编译器我知道这个类型」，编译时不验证，运行时可能出错
- 类型守卫（`typeof`/`instanceof`/`in`/`is`）是「通过运行时判断来收窄类型」，是真正的类型检查
- 断言是开发者主观判断，守卫是程序客观判断，推荐优先使用守卫

**Q8：如何为第三方 JS 库添加类型声明？**
- 优先安装官方类型包：`npm i -D @types/xxx`
- 没有官方类型包时，编写自定义 `.d.ts` 文件，使用 `declare module 'xxx'`
- 全局变量使用 `declare global` 或 `declare interface Window` 扩展
