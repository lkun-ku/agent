# Vue 框架复习

> Vue 是渐进式 JavaScript 框架，Vue3 引入组合式 API，性能更好、TypeScript 支持更完善。

## 一、Vue 简介

### 1.1 Vue 是什么

Vue 是一套用于构建用户界面的**渐进式** JavaScript 框架，核心特点：

- **声明式渲染**：通过模板语法扩展 HTML，声明式地把数据渲染进 DOM
- **组件化应用**：将界面拆分为独立可复用的组件，每个组件包含视图、数据、逻辑
- **渐进式**：可按需引入路由（Vue Router）、状态管理（Pinia）、构建工具（Vite）等生态

```html
<div id="app">
  <p>{{ message }}</p>
  <button @click="message = '你好 Vue'">点击修改</button>
</div>
```

### 1.2 Vue2 vs Vue3 的主要区别

| 对比项 | Vue2 | Vue3 |
| --- | --- | --- |
| API 风格 | 选项式 API（Options API） | 组合式 API（Composition API）+ 选项式 API |
| 响应式原理 | `Object.defineProperty` | `Proxy` |
| 多根节点 | 不支持（必须单根） | 支持 Fragment |
| 生命周期 | beforeDestroy / destroyed | beforeUnmount / unmounted |
| 状态管理 | Vuex | Pinia |
| TypeScript | 支持较弱 | 原生支持更好 |
| Tree-shaking | 不支持 | 支持（按需引入） |
| 新内置组件 | - | Teleport、Suspense |
| 性能 | - | 打包体积更小、渲染更快 |

> ⚠️ Vue3 使用 Proxy 无法监听 IE，且不再支持 IE11 及以下浏览器

---

## 二、Vue3 组合式 API

### 2.1 setup 选项

`setup` 是组合式 API 的入口，**执行时机在 beforeCreate 之前**，此时组件实例尚未创建，无法使用 `this`。

**两种写法：**

```vue
<!-- 写法一：setup() 函数 -->
<script>
import { ref } from 'vue'
export default {
  setup() {
    const count = ref(0)
    return { count }  // 暴露给模板
  }
}
</script>

<!-- 写法二：<script setup> 语法糖（推荐） -->
<script setup>
import { ref } from 'vue'
const count = ref(0)  // 顶层声明自动暴露给模板
</script>
```

> 💡 `<script setup>` 是官方推荐写法，无需 return，代码更简洁，编译后性能更好

### 2.2 响应式数据

**ref：** 用于基本类型和引用类型，**需通过 `.value` 访问**

```vue
<script setup>
import { ref } from 'vue'
const count = ref(0)         // 基本类型
const user = ref({ name: '张三' })  // 引用类型

const add = () => count.value++
const changeName = () => user.value.name = '李四'
</script>

<template>
  <p>{{ count }}</p>          <!-- 模板中自动解包，无需 .value -->
  <p>{{ user.name }}</p>
  <button @click="add">+1</button>
</template>
```

**reactive：** 仅用于对象/数组，**直接访问属性**，无需 `.value`

```vue
<script setup>
import { reactive } from 'vue'
const state = reactive({
  count: 0,
  list: ['a', 'b']
})
const add = () => state.count++
</script>
```

**ref vs reactive 对比：**

| 特性 | ref | reactive |
| --- | --- | --- |
| 适用类型 | 基本类型 + 引用类型 | 仅对象/数组 |
| 访问方式 | JS 中需 `.value`，模板自动解包 | 直接访问属性 |
| 响应式原理 | 内部基于 `RefImpl`，对象类型也用 Proxy | 基于 `Proxy` |
| 解构响应式 | 解构后仍响应（基本类型也保持） | 解构后**失去响应式**（需 `toRefs`） |
| 推荐场景 | 单值、需重新赋值的对象 | 表单、复杂对象 |

> ⚠️ reactive 对象**不能直接整体替换**，会丢失响应式；如需替换用 `Object.assign(state, newObj)` 或改用 ref

### 2.3 computed 计算属性

```vue
<script setup>
import { ref, computed } from 'vue'
const firstName = ref('张')
const lastName = ref('三')

// 只读计算属性
const fullName = computed(() => firstName.value + lastName.value)

// 可读可写计算属性
const fullName2 = computed({
  get() {
    return firstName.value + lastName.value
  },
  set(val) {
    firstName.value = val[0]
    lastName.value = val.slice(1)
  }
})
</script>
```

> 💡 计算属性基于响应式依赖缓存，依赖不变时多次访问只执行一次；methods 每次调用都执行

### 2.4 watch 侦听器

```vue
<script setup>
import { ref, watch, watchEffect, reactive } from 'vue'
const count = ref(0)
const user = reactive({ name: '张三', info: { age: 18 } })

// 1. 监听 ref
watch(count, (newVal, oldVal) => {
  console.log('count 变了', newVal, oldVal)
})

// 2. 监听 reactive 默认深度监听
watch(user, (newVal) => {
  console.log('user 变了', newVal)
}, { deep: true })  // reactive 默认就是深度监听

// 3. 监听对象的某个属性（需用函数返回）
watch(() => user.name, (newVal) => {
  console.log('name 变了', newVal)
})

// 4. immediate 立即执行
watch(count, (newVal) => {
  console.log('立即执行', newVal)
}, { immediate: true })

// 5. watchEffect：自动收集依赖 + 立即执行
watchEffect(() => {
  console.log('count:', count.value)  // 自动收集 count 依赖
})
</script>
```

**watch vs watchEffect 对比：**

| 特性 | watch | watchEffect |
| --- | --- | --- |
| 依赖收集 | 手动指定 | 自动收集 |
| 执行时机 | 默认数据变化时执行 | 立即执行一次 |
| 获取旧值 | 可获取 `oldVal` | 无法获取旧值 |
| 使用场景 | 需要旧值、明确监听源 | 副作用、多依赖自动追踪 |

> ⚠️ 监听 ref 对象类型时，`deep: true` 才能深度监听属性变化；监听 reactive 默认深度

### 2.5 生命周期

```vue
<script setup>
import { onMounted, onUpdated, onUnmounted } from 'vue'

onMounted(() => {
  console.log('组件挂载完成，可操作 DOM')
})
onUpdated(() => {
  console.log('组件更新完成')
})
onUnmounted(() => {
  console.log('组件卸载，清除定时器/事件监听')
})
</script>
```

| Vue2 | Vue3（setup 中） | 说明 |
| --- | --- | --- |
| beforeCreate | setup | 创建前（setup 代替） |
| created | setup | 创建后（setup 代替） |
| beforeMount | onBeforeMount | 挂载前 |
| mounted | onMounted | 挂载后 |
| beforeUpdate | onBeforeUpdate | 更新前 |
| updated | onUpdated | 更新后 |
| beforeDestroy | onBeforeUnmount | 卸载前 |
| destroyed | onUnmounted | 卸载后 |

> 💡 父子组件生命周期执行顺序：挂载时父 beforeMount → 子 beforeMount → 子 mounted → 父 mounted

---

## 三、指令

### 3.1 模板语法

```vue
<template>
  <!-- 插值表达式 -->
  <p>{{ message }}</p>

  <!-- v-bind 属性绑定（简写 :） -->
  <img :src="imgUrl" :alt="title">
  <div :class="{ active: isActive }" :style="{ color: 'red' }">

  <!-- v-on 事件绑定（简写 @） -->
  <button @click="handleClick">点击</button>
  <input @input="handleInput" @keyup.enter="submit">

  <!-- v-model 双向绑定 -->
  <input v-model="message" type="text">
</template>
```

### 3.2 条件渲染

```vue
<template>
  <!-- v-if 系列：销毁/创建 DOM -->
  <p v-if="score >= 90">优秀</p>
  <p v-else-if="score >= 60">及格</p>
  <p v-else>不及格</p>

  <!-- v-show：display:none 切换 -->
  <p v-show="isVisible">显示/隐藏</p>
</template>
```

| 特性 | v-if | v-show |
| --- | --- | --- |
| 原理 | 动态创建/销毁 DOM | `display: none` 切换 |
| 初始渲染 | false 时不渲染 | 始终渲染，仅切换样式 |
| 切换开销 | 高（重新创建） | 低（仅样式） |
| 首次开销 | 低 | 高 |
| 适用场景 | 不频繁切换 | 频繁切换 |

> ⚠️ v-if 和 v-for 不应同时用在同一元素，v-if 优先级高于 v-for（Vue3）会导致无法访问 v-for 中的变量

### 3.3 列表渲染

```vue
<script setup>
import { ref } from 'vue'
const list = ref([
  { id: 1, name: '张三' },
  { id: 2, name: '李四' },
  { id: 3, name: '王五' }
])
</script>

<template>
  <!-- 必须加 key，且唯一稳定 -->
  <li v-for="(item, index) in list" :key="item.id">
    {{ index }} - {{ item.name }}
  </li>

  <!-- 遍历对象 -->
  <li v-for="(value, key) in obj" :key="key">{{ key }}: {{ value }}</li>
</template>
```

> ⚠️ key 必须唯一且稳定，**禁止用 index 作为 key**，否则数据错乱、复用错误

### 3.4 其他指令

| 指令 | 说明 |
| --- | --- |
| `v-text` | 设置文本内容（等价 `{{ }}`） |
| `v-html` | 设置 innerHTML（可解析 HTML 标签，⚠️ 有 XSS 风险） |
| `v-cloak` | 配合 CSS `[v-cloak]{display:none}` 防止插值闪现 |
| `v-once` | 元素只渲染一次，后续更新不变化 |
| `v-pre` | 跳过编译，原样输出 `{{ }}` |

### 3.5 修饰符

**事件修饰符：**

```vue
<!-- 阻止冒泡 -->
<button @click.stop="handle">阻止冒泡</button>
<!-- 阻止默认行为 -->
<a @click.prevent="handle">阻止默认</a>
<!-- 仅当事件目标为自身时触发 -->
<div @click.self="handle">self</div>
<!-- 只触发一次 -->
<button @click.once="handle">once</button>
<!-- 捕获阶段触发 -->
<div @click.capture="handle">capture</div>
<!-- 滚动默认行为立即执行（提升性能） -->
<div @scroll.passive="handle">passive</div>
```

**按键修饰符：**

```vue
<input @keyup.enter="submit">   <!-- 回车 -->
<input @keyup.esc="cancel">     <!-- Esc -->
<input @keyup.space="handle">   <!-- 空格 -->
```

**v-model 修饰符：**

```vue
<input v-model.lazy="msg">      <!-- 失焦或回车才同步 -->
<input v-model.number="num">    <!-- 转为数字 -->
<input v-model.trim="msg">      <!-- 去除首尾空格 -->
```

---

## 四、组件化

### 4.1 组件注册

```vue
<!-- 全局注册（main.js） -->
<script>
import { createApp } from 'vue'
import App from './App.vue'
import MyButton from './MyButton.vue'

const app = createApp(App)
app.component('MyButton', MyButton)  // 全局注册，任意地方可用
app.mount('#app')
</script>

<!-- 局部注册：<script setup> 中直接 import 使用 -->
<script setup>
import MyButton from './MyButton.vue'  // 自动注册，模板直接用
</script>

<template>
  <MyButton />
</template>
```

### 4.2 组件通信方式总览

| 方式 | 方向 | 说明 |
| --- | --- | --- |
| props / emit | 父 ↔ 子 | 父传属性，子触发事件 |
| v-model | 父 ↔ 子 | 双向绑定（语法糖） |
| ref | 父 → 子 | 父直接获取子组件实例 |
| provide / inject | 祖 → 后 | 跨层级传递 |
| mitt / EventBus | 任意 | 事件总线（Vue3 需第三方库） |
| Pinia | 任意 | 状态管理 |

### 4.3 props 父传子

```vue
<!-- 父组件 -->
<script setup>
import { ref } from 'vue'
import Child from './Child.vue'
const msg = ref('来自父组件的数据')
</script>

<template>
  <Child :msg="msg" :age="18" />
</template>

<!-- 子组件 Child.vue -->
<script setup>
defineProps({
  msg: String,           // 类型
  age: {
    type: Number,
    default: 0,          // 默认值
    required: true,      // 必填
    validator: (v) => v >= 0  // 校验
  }
})
</script>

<template>
  <p>{{ msg }} - {{ age }}</p>
</template>
```

> ⚠️ props 是只读的，子组件不能直接修改父组件传来的 props（单向数据流）

### 4.4 emit 子传父

```vue
<!-- 子组件 -->
<script setup>
const emit = defineEmits(['change', 'update'])
const handleClick = () => {
  emit('change', '子组件数据')  // 触发事件并传参
}
</script>

<!-- 父组件 -->
<script setup>
import Child from './Child.vue'
const onChange = (val) => console.log('收到', val)
</script>

<template>
  <Child @change="onChange" />
</template>
```

### 4.5 模板引用 ref

```vue
<!-- 获取 DOM 元素 -->
<script setup>
import { ref } from 'vue'
const domRef = ref(null)
const childRef = ref(null)

const handleFocus = () => domRef.value.focus()
const callChildMethod = () => childRef.value.sayHi()  // 调用子组件方法
</script>

<template>
  <input ref="domRef" />
  <Child ref="childRef" />
</template>

<!-- 子组件需 defineExpose 暴露内容 -->
<script setup>
const sayHi = () => console.log('hi')
defineExpose({ sayHi })  // ⚠️ <script setup> 默认不暴露，需手动 expose
</script>
```

> ⚠️ `<script setup>` 中子组件默认对外封闭，父组件用 ref 拿不到内部属性方法，必须用 `defineExpose` 暴露

### 4.6 provide / inject 跨层级

```vue
<!-- 祖先组件 -->
<script setup>
import { ref, provide } from 'vue'
const theme = ref('dark')
const user = ref({ name: '张三' })

provide('theme', theme)        // 提供数据
provide('user', user)
provide('updateName', (val) => user.value.name = val)  // 提供方法供后代修改
</script>

<!-- 后代组件（任意层级） -->
<script setup>
import { inject } from 'vue'
const theme = inject('theme', 'light')        // 第二个参数为默认值
const user = inject('user')
const updateName = inject('updateName')
</script>
```

### 4.7 插槽 slot

```vue
<!-- 默认插槽 -->
<!-- 父 -->
<Card>
  <p>这是卡片内容</p>
</Card>
<!-- 子 Card.vue -->
<template>
  <div class="card">
    <slot></slot>  <!-- 接收内容 -->
  </div>
</template>

<!-- 具名插槽 -->
<!-- 父 -->
<Layout>
  <template #header>
    <h1>标题</h1>
  </template>
  <template #footer>
    <p>底部</p>
  </template>
</Layout>
<!-- 子 Layout.vue -->
<template>
  <div>
    <header><slot name="header"></slot></header>
    <main><slot></slot></main>
    <footer><slot name="footer"></slot></footer>
  </div>
</template>

<!-- 作用域插槽（子传父数据） -->
<!-- 子 List.vue -->
<template>
  <ul>
    <li v-for="item in list" :key="item.id">
      <slot :item="item" :index="index"></slot>
    </li>
  </ul>
</template>
<!-- 父 -->
<List :list="list">
  <template #default="{ item, index }">
    <span>{{ index }}: {{ item.name }}</span>
  </template>
</List>
```

---

## 五、Vue Router

### 5.1 路由配置

```js
// router/index.js
import { createRouter, createWebHistory } from 'vue-router'
import Home from '@/views/Home.vue'

const router = createRouter({
  history: createWebHistory(),  // history 模式
  routes: [
    { path: '/', redirect: '/home' },
    { path: '/home', name: 'home', component: Home },
    {
      path: '/user',
      component: () => import('@/views/User.vue'),  // 路由懒加载
      children: [  // 嵌套路由
        { path: 'info', component: () => import('@/views/UserInfo.vue') }
      ]
    }
  ]
})

export default router
```

```js
// main.js
import { createApp } from 'vue'
import App from './App.vue'
import router from './router'

createApp(App).use(router).mount('#app')
```

### 5.2 路由跳转

```vue
<script setup>
import { useRouter } from 'vue-router'
const router = useRouter()

const goAbout = () => {
  router.push('/about')                      // 编程式跳转，可返回
  router.push({ path: '/user', query: { id: 1 } })
  router.replace('/login')                   // 替换，不可返回
  router.back()                              // 返回上一页
  router.forward()                           // 前进
}
</script>

<template>
  <!-- 声明式跳转 -->
  <router-link to="/home">首页</router-link>
  <router-link :to="{ path: '/user', query: { id: 1 } }">用户</router-link>
  <router-link to="/home" replace>替换跳转</router-link>

  <!-- 路由出口 -->
  <router-view />
</template>
```

### 5.3 动态路由

```js
// 路由配置
{ path: '/user/:id', component: User }
```

```vue
<!-- User.vue -->
<script setup>
import { useRoute } from 'vue-router'
const route = useRoute()
console.log(route.params.id)  // 获取路径参数
console.log(route.query.q)    // 获取 query 参数
</script>
```

### 5.4 嵌套路由

```js
{
  path: '/layout',
  component: Layout,
  children: [
    { path: '', redirect: '/layout/home' },  // 默认重定向
    { path: 'home', component: Home },       // /layout/home
    { path: 'category', component: Category } // /layout/category
  ]
}
```

```vue
<!-- Layout.vue -->
<template>
  <header>导航</header>
  <router-view />  <!-- 子路由出口 -->
</template>
```

### 5.5 路由守卫

```js
// 全局前置守卫（常用于登录权限校验）
router.beforeEach((to, from) => {
  const token = localStorage.getItem('token')
  if (!token && to.path !== '/login') {
    return '/login'  // 重定向到登录页
  }
  // 返回 false 取消导航；返回路径/对象重定向；不返回或 true 放行
})

// 全局后置钩子
router.afterEach((to, from) => {
  document.title = to.meta.title || '默认标题'
})

// 路由独享守卫
{
  path: '/admin',
  component: Admin,
  beforeEnter: (to, from) => {
    // 仅对该路由生效
  }
}
```

```vue
<!-- 组件内守卫（setup 中） -->
<script setup>
import { onBeforeRouteLeave, onBeforeRouteUpdate } from 'vue-router'

onBeforeRouteLeave((to, from) => {
  const answer = window.confirm('确定离开吗？未保存数据将丢失')
  if (!answer) return false
})

onBeforeRouteUpdate((to, from) => {
  // 路由参数变化但复用同一组件时触发
})
</script>
```

### 5.6 路由模式

| 模式 | URL 形式 | 兼容性 | 服务端配置 |
| --- | --- | --- | --- |
| hash | `http://xxx/#/home` | 兼容性好（靠 `#` 后变化） | 无需配置 |
| history | `http://xxx/home` | URL 无 `#` 更美观 | 需配置（否则刷新 404） |

> ⚠️ history 模式部署到服务器需配置回退到 `index.html`（Nginx: `try_files $uri $uri/ /index.html;`）

---

## 六、Pinia 状态管理

### 6.1 Pinia vs Vuex

| 对比项 | Vuex | Pinia |
| --- | --- | --- |
| 模块化 | 需要 modules 嵌套 | 每个 store 独立平级 |
| mutations | 修改 state 必须经 mutations | 直接修改，无 mutations |
| TypeScript | 支持较弱 | 完美 TS 推断 |
| API 风格 | 选项式 | 选项式 + 组合式 |
| 体积 | 较大 | 更小（约 1KB） |
| 命名空间 | 需要 `namespaced: true` | 无需，store 自带命名 |
| Composition API | 支持有限 | 原生支持 |

### 6.2 定义 Store

**选项式写法：**

```js
// stores/counter.js
import { defineStore } from 'pinia'

export const useCounterStore = defineStore('counter', {
  state: () => ({
    count: 0,
    list: []
  }),
  getters: {
    double: (state) => state.count * 2,
    // 访问其他 getter
    doublePlusOne() {
      return this.double + 1
    }
  },
  actions: {
    increment() {
      this.count++
    },
    // 支持异步
    async fetchList() {
      const res = await api.getList()
      this.list = res.data
    }
  }
})
```

**组合式写法（推荐）：**

```js
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useCounterStore = defineStore('counter', () => {
  const count = ref(0)              // 相当于 state
  const list = ref([])

  const double = computed(() => count.value * 2)  // 相当于 getters

  const increment = () => {          // 相当于 actions
    count.value++
  }

  return { count, list, double, increment }
})
```

### 6.3 使用 Store

```vue
<script setup>
import { useCounterStore } from '@/stores/counter'
import { storeToRefs } from 'pinia'

const store = useCounterStore()

// 1. 直接读取
console.log(store.count)

// 2. 修改 state
store.count++                         // 方式一：直接修改
store.$patch({ count: 10, list: [] }) // 方式二：$patch 批量修改
store.increment()                     // 方式三：调用 action

// 3. 解构（保持响应式需 storeToRefs）
const { count, double } = storeToRefs(store)
// ⚠️ 直接解构会失去响应式：const { count } = store（错误）
const { increment } = store           // 方法可直接解构（无需 storeToRefs）
</script>

<template>
  <p>{{ count }} - {{ double }}</p>
  <button @click="increment">+1</button>
</template>
```

### 6.4 storeToRefs 保持响应式解构

> ⚠️ 解构 store 的 state/getter 会失去响应式，必须用 `storeToRefs`；解构 action 可直接解构

```js
import { storeToRefs } from 'pinia'

const store = useCounterStore()
const { count, double } = storeToRefs(store)  // ✅ 保持响应式
const { increment } = store                   // ✅ action 直接解构
```

---

## 七、Vue3 项目实战要点

### 7.1 项目创建

```bash
# 使用 create-vue 脚手架（官方推荐）
npm create vue@latest

# 使用 Vite 创建
npm create vite@latest my-vue-app -- --template vue
```

### 7.2 目录结构

```
src/
├── api/          # 接口请求
├── assets/       # 静态资源
├── components/   # 公共组件
├── composables/  # 组合式函数（hooks）
├── router/       # 路由配置
├── stores/       # Pinia 状态管理
├── utils/        # 工具函数
├── views/        # 页面级组件
├── App.vue       # 根组件
└── main.js       # 入口文件
```

### 7.3 axios 封装

```js
// utils/request.js
import axios from 'axios'
import { useUserStore } from '@/stores/user'
import router from '@/router'

const request = axios.create({
  baseURL: 'http://api.example.com',
  timeout: 5000
})

// 请求拦截器：统一携带 token
request.interceptors.request.use((config) => {
  const userStore = useUserStore()
  if (userStore.token) {
    config.headers.Authorization = `Bearer ${userStore.token}`
  }
  return config
})

// 响应拦截器：统一错误处理
request.interceptors.response.use(
  (response) => response.data,  // 直接返回业务数据
  (error) => {
    if (error.response?.status === 401) {
      router.push('/login')  // 401 跳转登录
    }
    return Promise.reject(error)
  }
)

export default request
```

### 7.4 路由配置与权限控制

```js
// router/index.js
const routes = [
  { path: '/login', component: () => import('@/views/Login.vue') },
  { path: '/', component: Layout, children: [
    { path: '', component: Home, meta: { requiresAuth: true } }
  ]}
]

router.beforeEach((to) => {
  const token = localStorage.getItem('token')
  if (to.meta.requiresAuth && !token) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }
})
```

### 7.5 状态管理（用户、购物车）

```js
// stores/user.js
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { loginApi } from '@/api/user'

export const useUserStore = defineStore('user', () => {
  const userInfo = ref({})
  const token = ref(localStorage.getItem('token') || '')

  const login = async (form) => {
    const res = await loginApi(form)
    token.value = res.token
    userInfo.value = res.userInfo
    localStorage.setItem('token', res.token)
  }

  const logout = () => {
    token.value = ''
    userInfo.value = {}
    localStorage.removeItem('token')
  }

  return { userInfo, token, login, logout }
})
```

### 7.6 组件封装与复用

- **通用组件**：放在 `components/`，如按钮、弹窗、表单项
- **业务组件**：与具体页面绑定，放在 `views/` 对应子目录
- **组合式函数**：复用逻辑放 `composables/`，如 `useCart.js`、`useScroll.js`

```js
// composables/useCart.js —— 逻辑复用
import { ref, computed } from 'vue'

export function useCart() {
  const cartList = ref([])
  const totalCount = computed(() =>
    cartList.value.reduce((sum, item) => sum + item.count, 0)
  )

  const addCart = (goods) => { /* ... */ }

  return { cartList, totalCount, addCart }
}
```

```vue
<!-- 任意组件复用 -->
<script setup>
import { useCart } from '@/composables/useCart'
const { cartList, totalCount, addCart } = useCart()
</script>
```

---

## 💡 关联面试题

**Q1：Vue2 和 Vue3 的主要区别？**
- API 风格：Vue2 选项式，Vue3 组合式（更利于逻辑复用与组织）
- 响应式原理：Vue2 用 `Object.defineProperty`（无法监听新增属性/数组索引），Vue3 用 `Proxy`（全量监听）
- 性能：Vue3 支持 Tree-shaking、打包更小、渲染更快
- 新特性：Fragment（多根节点）、Teleport、Suspense、`<script setup>` 语法糖
- 生态：Vue3 推荐 Pinia 替代 Vuex，全面支持 TypeScript

**Q2：ref 和 reactive 的区别？什么时候用哪个？**
- ref：可包装基本类型和对象，JS 中需 `.value` 访问，模板自动解包；适合单值、需重新赋值的场景
- reactive：仅用于对象/数组，直接访问属性；适合表单、复杂对象
- 区别：reactive 解构会失去响应式（需 `toRefs`），且不能整体替换；ref 解构保持响应式
- 经验：基本类型必用 ref；对象两者都可，需重新赋值用 ref

**Q3：Vue3 组合式 API 相比选项式 API 有什么优势？**
- 逻辑聚合：相关代码集中在一起，而非分散在 data/methods/computed
- 逻辑复用：通过组合式函数（composables）干净复用，无 mixin 命名冲突
- 类型推断：TypeScript 支持更好
- 代码压缩：更利于 Tree-shaking

**Q4：watch 和 watchEffect 的区别？**
- 依赖：watch 需手动指定监听源，watchEffect 自动收集
- 执行时机：watch 默认数据变化才执行，watchEffect 立即执行一次
- 旧值：watch 可获取旧值，watchEffect 不能
- 场景：watch 适合精确监听，watchEffect 适合副作用、多依赖

**Q5：v-if 和 v-show 的区别？**
- v-if：真销毁/重建 DOM，初始 false 不渲染，切换开销大
- v-show：始终渲染，靠 `display:none` 切换，首次开销大
- 频繁切换用 v-show，条件少变用 v-if

**Q6：Vue 组件通信有哪些方式？**
- 父子：props / emit、v-model、ref
- 祖孙跨层：provide / inject
- 任意：mitt 事件总线、Pinia 状态管理
- 其他：`$attrs` 透传、模板 ref

**Q7：Vue 的生命周期钩子有哪些？**
- 创建：beforeCreate、created（Vue3 中由 setup 代替）
- 挂载：beforeMount / onBeforeMount、mounted / onMounted
- 更新：beforeUpdate / onBeforeUpdate、updated / onUpdated
- 卸载：beforeUnmount / onBeforeUnmount、unmounted / onUnmounted
- 常用场景：mounted 请求数据、mounted 操作 DOM、unmounted 清除定时器

**Q8：Pinia 和 Vuex 的区别？**
- Pinia 去除 mutations，可直接修改 state
- 无需 modules 嵌套，每个 store 平级独立
- 完美 TypeScript 推断
- 支持 Composition API 风格
- 体积更小，API 更简洁

**Q9：Vue Router 的 hash 和 history 模式区别？**
- hash：URL 带 `#`，靠 `hashchange` 事件，兼容性好，无需服务端配置
- history：URL 无 `#`，靠 `pushState`/`popstate`，更美观，但刷新需服务端配置回退到 index.html

**Q10：v-for 中 key 的作用是什么？**
- key 是虚拟 DOM diff 算法识别节点的唯一标识
- 正确的 key 可高效复用节点、减少 DOM 操作、避免数据错乱
- 禁止用 index 作为 key（数据增删会导致复用错误、状态错乱）
- 推荐用数据中稳定唯一的 id
