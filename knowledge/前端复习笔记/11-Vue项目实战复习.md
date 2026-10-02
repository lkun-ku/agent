# Vue 项目实战复习

> 基于 Vue 人力资源项目（vue-element-admin 模板）的中后台管理系统实战总结，涵盖项目架构、路由权限、状态管理、请求封装、文件上传、ECharts 图表与 Nginx 部署等核心知识。

## 一、项目架构

### 1.1 vue-element-admin 模板介绍

- 基于 Vue2 + Element UI 的中后台解决方案
- 核心特性：权限验证、动态路由、主题切换、国际化、Mock 数据

| 特性 | 说明 |
| --- | --- |
| 权限验证 | 基于 token + 角色，路由守卫拦截 |
| 动态路由 | 根据用户角色动态加载路由表 |
| 主题切换 | 通过 settings.js 切换侧边栏主题 |
| 国际化 | i18n 多语言支持 |
| Mock 数据 | 内置 mockjs，无需后端即可调试 |

### 1.2 项目目录结构

```
src/
├── api/           # 接口请求
├── assets/        # 静态资源
├── components/    # 全局组件
├── icons/         # SVG 图标
├── layout/        # 布局组件
├── router/        # 路由配置
├── store/         # Vuex 状态管理
├── styles/        # 全局样式
├── utils/         # 工具函数
├── views/         # 页面视图
├── App.vue        # 根组件
├── main.js        # 入口文件
├── permission.js  # 路由守卫（权限控制）
└── settings.js    # 全局配置
```

### 1.3 settings.js 全局配置

```js
module.exports = {
  title: '人力资源管理后台', // 网站标题
  showSettings: true,        // 是否显示右上角设置按钮
  tagsView: true,            // 是否显示标签页
  fixedHeader: false,        // 是否固定 Header
  sidebarLogo: true,         // 是否显示侧边栏 Logo
  errorLog: 'production'     // 错误日志环境
}
```

> 💡 修改后页面右上角设置面板会同步响应，配置项会被持久化到 Cookie 中

### 1.4 环境变量配置

| 文件 | 作用 | 示例变量 |
| --- | --- | --- |
| `.env.development` | 开发环境 | `VUE_APP_BASE_API = '/api'` |
| `.env.production` | 生产环境 | `VUE_APP_BASE_API = '/prod-api'` |
| `.env.staging` | 预发布环境 | `VUE_APP_BASE_API = '/stage-api'` |

```bash
# .env.development
VUE_APP_BASE_API = '/api'
```

```js
// 在 axios 实例中使用
const service = axios.create({
  baseURL: process.env.VUE_APP_BASE_API,
  timeout: 5000
})
```

---

## 二、路由与权限控制（重点）

### 2.1 路由守卫 permission.js

```js
import router from './router'
import store from './store'
import { getToken } from '@/utils/auth'

const whiteList = ['/login', '/404'] // 白名单

router.beforeEach(async (to, from, next) => {
  // 1. 获取 token
  const hasToken = getToken()

  if (hasToken) {
    if (to.path === '/login') {
      next({ path: '/' }) // 已登录跳转主页
    } else {
      // 2. 判断是否已获取用户信息
      const hasUserInfo = store.getters.name
      if (hasUserInfo) {
        next()
      } else {
        try {
          // 3. 获取用户信息（包含 roles）
          await store.dispatch('user/getInfo')
          // 4. 根据角色生成动态路由
          const accessRoutes = await store.dispatch('permission/generateRoutes')
          // 5. 动态添加路由
          router.addRoutes(accessRoutes)
          // ⚠️ addRoutes 后需 replace，确保新路由生效
          next({ ...to, replace: true })
        } catch (error) {
          // token 失效，清空后跳登录
          await store.dispatch('user/resetToken')
          next(`/login?redirect=${to.path}`)
        }
      }
    }
  } else {
    // 无 token：白名单放行，否则跳登录
    if (whiteList.includes(to.path)) {
      next()
    } else {
      next(`/login?redirect=${to.path}`)
    }
  }
})
```

> ⚠️ **易错点**：`router.addRoutes()` 后必须使用 `next({ ...to, replace: true })`，否则新添加的路由可能不生效

### 2.2 动态路由

```js
// store/modules/permission.js
import { asyncRoutes, constantRoutes } from '@/router'

function hasPermission(roles, route) {
  if (route.meta && route.meta.roles) {
    return roles.some(role => route.meta.roles.includes(role))
  } else {
    return true // 没有配置 roles 默认所有人可见
  }
}

export default {
  state: {
    routes: [],          // 最终渲染的路由
    addRoutes: []        // 动态添加的路由
  },
  mutations: {
    SET_ROUTES: (state, routes) => {
      state.addRoutes = routes
      state.routes = constantRoutes.concat(routes)
    }
  },
  actions: {
    generateRoutes({ commit }, roles) {
      return new Promise(resolve => {
        let accessedRoutes
        if (roles.includes('admin')) {
          accessedRoutes = asyncRoutes // admin 拥有全部路由
        } else {
          accessedRoutes = filterAsyncRoutes(asyncRoutes, roles)
        }
        commit('SET_ROUTES', accessedRoutes)
        resolve(accessedRoutes)
      })
    }
  }
}

// 递归过滤异步路由
export function filterAsyncRoutes(routes, roles) {
  const res = []
  routes.forEach(route => {
    const tmp = { ...route }
    if (hasPermission(roles, tmp)) {
      if (tmp.children) {
        tmp.children = filterAsyncRoutes(tmp.children, roles)
      }
      res.push(tmp)
    }
  })
  return res
}
```

### 2.3 路由模块化

```js
// router/index.js
export const constantRoutes = [
  {
    path: '/login',
    component: () => import('@/views/login/index'),
    hidden: true
  },
  {
    path: '/404',
    component: () => import('@/views/404'),
    hidden: true
  },
  {
    path: '/',
    component: Layout,
    redirect: '/dashboard',
    children: [{
      path: 'dashboard',
      name: 'Dashboard',
      component: () => import('@/views/dashboard/index'),
      meta: { title: '首页', icon: 'dashboard' }
    }]
  }
]

export const asyncRoutes = [
  {
    path: '/employee',
    component: Layout,
    children: [{
      path: '',
      name: 'Employee',
      component: () => import('@/views/employee/index'),
      meta: { title: '员工管理', icon: 'people', roles: ['admin', 'hr'] }
    }]
  },
  // ... 末尾必须放 404
  { path: '*', redirect: '/404', hidden: true }
]
```

| 路由类型 | 说明 | 是否过滤 |
| --- | --- | --- |
| `constantRoutes` | 静态路由（登录页、404、首页） | 否 |
| `asyncRoutes` | 异步路由（需权限判断的业务页面） | 是 |

> ⚠️ **易错点**：`{ path: '*', redirect: '/404' }` 必须放在 `asyncRoutes` 末尾，且在动态路由添加之后才能命中

### 2.4 权限指令 v-permission

```js
// main.js
import Vue from 'vue'
Vue.directive('permission', {
  inserted(el, binding) {
    const { value } = binding
    const roles = store.getters.roles

    if (value && value instanceof Array && value.length > 0) {
      const hasPermission = roles.some(role => value.includes(role))
      if (!hasPermission) {
        // 无权限则移除元素
        el.parentNode && el.parentNode.removeChild(el)
      }
    } else {
      throw new Error(`需要传入角色数组，如：v-permission="['admin','hr']"`)
    }
  }
})
```

```html
<!-- 使用：仅 admin 可见 -->
<el-button v-permission="['admin']" type="danger">删除</el-button>
```

---

## 三、Vuex 状态管理（模块化）

### 3.1 模块拆分

```
store/
├── modules/
│   ├── user.js        # 用户模块（token、用户信息）
│   ├── app.js         # 应用设置（侧边栏、设备类型）
│   ├── settings.js    # 布局设置
│   └── permission.js  # 权限路由
├── getters.js         # 全局 getters
└── index.js
```

```js
// store/index.js
import Vue from 'vue'
import Vuex from 'vuex'
import user from './modules/user'
import app from './modules/app'
import permission from './modules/permission'
import settings from './modules/settings'
import getters from './getters'

Vue.use(Vuex)

const store = new Vuex.Store({
  modules: { user, app, permission, settings },
  getters
})

export default store
```

### 3.2 用户模块 user.js

```js
import { login, logout, getInfo } from '@/api/user'
import { getToken, setToken, removeToken } from '@/utils/auth'
import { resetRouter } from '@/router'

const state = {
  token: getToken(),
  name: '',
  avatar: '',
  roles: []
}

const mutations = {
  SET_TOKEN: (state, token) => { state.token = token },
  SET_NAME: (state, name) => { state.name = name },
  SET_AVATAR: (state, avatar) => { state.avatar = avatar },
  SET_ROLES: (state, roles) => { state.roles = roles }
}

const actions = {
  // 登录
  login({ commit }, userInfo) {
    const { username, password } = userInfo
    return new Promise((resolve, reject) => {
      login({ username: username.trim(), password }).then(res => {
        const { data } = res
        commit('SET_TOKEN', data.token)
        setToken(data.token)
        resolve()
      }).catch(error => reject(error))
    })
  },

  // 获取用户信息
  getInfo({ commit, state }) {
    return new Promise((resolve, reject) => {
      getInfo(state.token).then(res => {
        const { data } = res
        if (!data) return reject('验证失败，请重新登录')
        const { roles, name, avatar } = data
        if (!roles || roles.length <= 0) reject('角色不能为空')
        commit('SET_ROLES', roles)
        commit('SET_NAME', name)
        commit('SET_AVATAR', avatar)
        resolve(data)
      }).catch(error => reject(error))
    })
  },

  // 退出登录
  logout({ commit, state }) {
    return new Promise((resolve, reject) => {
      logout(state.token).then(() => {
        commit('SET_TOKEN', '')
        commit('SET_ROLES', [])
        removeToken()
        resetRouter()
        resolve()
      }).catch(error => reject(error))
    })
  },

  // 重置 token
  resetToken({ commit }) {
    return new Promise(resolve => {
      commit('SET_TOKEN', '')
      commit('SET_ROLES', [])
      removeToken()
      resolve()
    })
  }
}

export default {
  namespaced: true,
  state,
  mutations,
  actions
}
```

### 3.3 token 持久化

```js
// utils/auth.js
import Cookies from 'js-cookie'

const TokenKey = 'hr_token'

export function getToken() {
  return Cookies.get(TokenKey)
}

export function setToken(token) {
  return Cookies.set(TokenKey, token, { expires: 7 }) // 7 天过期
}

export function removeToken() {
  return Cookies.remove(TokenKey)
}
```

| 存储方式 | 是否刷新丢失 | 容量 | 自动携带 |
| --- | --- | --- | --- |
| Vuex | 是 | 内存 | 否 |
| Cookie | 否 | 4KB | 是（请求自动带） |
| localStorage | 否 | 5MB | 否 |
| sessionStorage | 是（关标签页丢失） | 5MB | 否 |

> 💡 **为什么 Vuex 和 Cookie 双重存储？**
> - Vuex：方便组件中响应式访问 token（`store.getters.token`）
> - Cookie：刷新页面不丢失，且请求时自动携带（Authorization）

### 3.4 getters 快捷访问

```js
// store/getters.js
const getters = {
  sidebar: state => state.app.sidebar,
  device: state => state.app.device,
  token: state => state.user.token,
  avatar: state => state.user.avatar,
  name: state => state.user.name,
  roles: state => state.user.roles,
  permission_routes: state => state.permission.routes
}
export default getters
```

```js
// 组件中使用
computed: {
  ...mapGetters(['token', 'name', 'avatar', 'roles'])
}
```

---

## 四、axios 请求封装

### 4.1 request.js 封装

```js
import axios from 'axios'
import { Message, MessageBox } from 'element-ui'
import store from '@/store'
import { getToken } from '@/utils/auth'

// 创建 axios 实例
const service = axios.create({
  baseURL: process.env.VUE_APP_BASE_API, // 基地址
  timeout: 5000                           // 超时时间
})

// 请求拦截器：注入 token
service.interceptors.request.use(
  config => {
    if (store.getters.token) {
      config.headers['Authorization'] = 'Bearer ' + getToken()
    }
    return config
  },
  error => Promise.reject(error)
)

// 响应拦截器：统一错误处理
service.interceptors.response.use(
  response => {
    const res = response.data
    // 业务码非 20000 视为错误
    if (res.code !== 20000) {
      Message({ message: res.message || 'Error', type: 'error', duration: 5 * 1000 })

      // 50008: 非法 token  50014: token 过期
      if (res.code === 50008 || res.code === 50014) {
        MessageBox.confirm('登录状态已过期，请重新登录', '提示', {
          confirmButtonText: '重新登录',
          cancelButtonText: '取消',
          type: 'warning'
        }).then(() => {
          store.dispatch('user/resetToken').then(() => location.reload())
        })
      }
      return Promise.reject(new Error(res.message || 'Error'))
    } else {
      return res
    }
  },
  error => {
    Message({ message: error.message, type: 'error', duration: 5 * 1000 })
    return Promise.reject(error)
  }
)

export default service
```

| 拦截器 | 作用 |
| --- | --- |
| 请求拦截 | 自动注入 token、设置请求头、loading 等 |
| 响应拦截 | 统一错误提示、token 失效处理、数据脱壳 |

> ⚠️ **易错点**：响应拦截返回 `response.data` 后，业务代码中拿到的是已脱壳数据，无需再 `.data`

### 4.2 API 模块化

```js
// api/user.js
import request from '@/utils/request'

export function login(data) {
  return request({ url: '/vue-admin-template/user/login', method: 'post', data })
}

export function getInfo(token) {
  return request({ url: '/vue-admin-template/user/info', method: 'get', params: { token } })
}

export function logout() {
  return request({ url: '/vue-admin-template/user/logout', method: 'post' })
}
```

```js
// api/employee.js
import request from '@/utils/request'

export function getEmployeeList(params) {
  return request({ url: '/sys/user', method: 'get', params })
}

export function addEmployee(data) {
  return request({ url: '/sys/user', method: 'post', data })
}
```

### 4.3 跨域处理

```js
// vue.config.js
module.exports = {
  devServer: {
    port: 8080,
    open: true,
    proxy: {
      '/api': {
        target: 'http://ihrm-java.itheima.net', // 后端地址
        changeOrigin: true,                     // 改变源
        pathRewrite: { '^/api': '' }            // 重写路径
      }
    }
  }
}
```

| 环境 | 跨域方案 | 原理 |
| --- | --- | --- |
| 开发环境 | vue.config.js proxy | Node 服务器中转请求，绕过浏览器同源策略 |
| 生产环境 | Nginx 反向代理 | 服务器端转发，浏览器只请求同源地址 |

---

## 五、登录模块

### 5.1 登录流程

```
1. 表单校验 → 2. 调用 Vuex login action
→ 3. login 调用接口获取 token → 4. 存储到 Vuex + Cookie
→ 5. 跳转主页 → 6. 路由守卫触发 getInfo 获取用户信息
```

```js
// views/login/index.vue
methods: {
  handleLogin() {
    this.$refs.loginForm.validate(async valid => {
      if (!valid) return
      this.loading = true
      try {
        await this.$store.dispatch('user/login', this.loginForm)
        this.$router.push({ path: this.redirect || '/' })
      } catch (error) {
        this.$message.error('登录失败')
      } finally {
        this.loading = false
      }
    })
  }
}
```

### 5.2 登录组件

```html
<template>
  <el-form ref="loginForm" :model="loginForm" :rules="loginRules" class="login-form">
    <el-form-item prop="username">
      <el-input v-model="loginForm.username" placeholder="用户名" prefix-icon="el-icon-user" />
    </el-form-item>
    <el-form-item prop="password">
      <el-input
        v-model="loginForm.password"
        type="password"
        placeholder="密码"
        prefix-icon="el-icon-lock"
        @keyup.enter.native="handleLogin"
      />
    </el-form-item>
    <el-button type="primary" :loading="loading" style="width:100%" @click="handleLogin">
      登录
    </el-button>
  </el-form>
</template>

<script>
export default {
  data() {
    return {
      loginForm: { username: 'admin', password: '123456' },
      loginRules: {
        username: [{ required: true, trigger: 'blur', message: '请输入用户名' }],
        password: [
          { required: true, trigger: 'blur', message: '请输入密码' },
          { min: 6, max: 16, trigger: 'blur', message: '密码长度 6-16 位' }
        ]
      },
      loading: false
    }
  }
}
</script>
```

> 💡 **Element UI 表单校验三要素**：`el-form` 绑定 `:rules`、`el-form-item` 配置 `prop`、`rules` 中定义校验规则

### 5.3 退出登录

```js
async handleLogout() {
  await this.$confirm('确认退出登录？', '提示', { type: 'warning' })
  await this.$store.dispatch('user/logout')
  this.$router.push('/login')
}
```

---

## 六、Layout 布局

### 6.1 布局结构

```html
<!-- layout/index.vue -->
<template>
  <div class="app-wrapper">
    <sidebar class="sidebar-container" />
    <div class="main-container">
      <div class="fixed-header">
        <navbar />
        <tags-view />
      </div>
      <app-main />
    </div>
  </div>
</template>
```

| 组件 | 作用 |
| --- | --- |
| `Sidebar` | 侧边栏菜单，根据路由动态渲染 |
| `Navbar` | 顶部导航栏（面包屑、用户头像、退出） |
| `AppMain` | 主内容区，`<router-view>` 出口 |
| `TagsView` | 标签页（多页签切换） |

### 6.2 侧边栏

```html
<!-- layout/components/Sidebar/index.vue -->
<template>
  <div class="sidebar-container">
    <el-menu
      :default-active="activeMenu"
      :collapse="isCollapse"
      :background-color="variables.menuBg"
      :unique-opened="false"
      router
    >
      <sidebar-item
        v-for="route in permission_routes"
        :key="route.path"
        :item="route"
        :base-path="route.path"
      />
    </el-menu>
  </div>
</template>
```

> 💡 菜单根据 `permission_routes`（Vuex 中合并的静态 + 动态路由）递归渲染，使用 `router` 模式自动跳转

### 6.3 面包屑导航

```html
<!-- layout/components/Navbar/Breadcrumb.vue -->
<template>
  <el-breadcrumb class="app-breadcrumb" separator="/">
    <transition-group name="breadcrumb">
      <el-breadcrumb-item v-for="(item, index) in levelList" :key="item.path">
        <span v-if="index === levelList.length - 1" class="no-redirect">{{ item.meta.title }}</span>
        <a v-else @click.prevent="handleLink(item)">{{ item.meta.title }}</a>
      </el-breadcrumb-item>
    </transition-group>
  </el-breadcrumb>
</template>
```

### 6.4 标签页 TagsView

```js
// 通过监听路由变化，缓存已访问的页面
watch: {
  $route() {
    this.addTags()
  }
},
methods: {
  addTags() {
    const { name } = this.$route
    if (name) this.$store.dispatch('tagsView/addView', this.$route)
  }
}
```

> ⚠️ **易错点**：`<keep-alive>` 缓存的组件名必须与路由 `name` 一致，否则缓存失效

---

## 七、组织架构（树形结构）

### 7.1 树形组件

```html
<el-tree
  :data="treeData"
  :props="{ label: 'name', children: 'children' }"
  node-key="id"
  default-expand-all
  @node-click="handleNodeClick"
/>
```

| 属性 | 说明 |
| --- | --- |
| `:data` | 树形数据源 |
| `:props` | 配置节点字段映射 |
| `node-key` | 节点唯一标识（必须） |
| `default-expand-all` | 默认展开全部 |
| `show-checkbox` | 显示复选框 |
| `check-strictly` | 父子不关联（角色权限分配常用） |

```js
// 标准树形数据结构
const treeData = [
  {
    id: '1',
    name: '总公司',
    children: [
      { id: '1-1', name: '研发部', children: [] },
      { id: '1-2', name: '财务部', children: [] }
    ]
  }
]
```

### 7.2 树形数据增删改查

```js
// 新增部门
async handleAdd(node) {
  await this.$refs.addDept.form.validate()
  await addDepartment({
    ...this.form,
    pid: node.id  // 父级 id
  })
  this.$message.success('新增成功')
  this.getDepartments() // 重新拉取
}

// 编辑部门
async handleEdit() {
  await updateDepartment(this.form)
  this.$message.success('修改成功')
  this.getDepartments()
}

// 删除部门（后端校验是否有子节点）
async handleDel(node) {
  await this.$confirm('确认删除该部门吗？')
  await delDepartment(node.id)
  this.$message.success('删除成功')
  this.getDepartments()
}
```

> ⚠️ **易错点**：删除部门前必须由后端校验是否存在子部门或员工，前端不能直接递归删除

### 7.3 递归处理树形数据

```js
// 递归遍历树：找到指定节点
function findNode(tree, id) {
  for (const node of tree) {
    if (node.id === id) return node
    if (node.children && node.children.length) {
      const result = findNode(node.children, id)
      if (result) return result
    }
  }
  return null
}

// 递归转扁平数组
function treeToArr(tree, result = []) {
  tree.forEach(node => {
    result.push(node)
    if (node.children && node.children.length) {
      treeToArr(node.children, result)
    }
  })
  return result
}

// 扁平数组转树（pid 关联）
function arrToTree(arr, pid = '') {
  return arr
    .filter(item => item.pid === pid)
    .map(item => ({ ...item, children: arrToTree(arr, item.id) }))
}
```

---

## 八、角色与员工管理

### 8.1 角色管理

```html
<!-- 角色列表 -->
<el-table :data="roleList" border>
  <el-table-column label="角色名称" prop="name" />
  <el-table-column label="描述" prop="description" />
  <el-table-column label="操作">
    <template slot-scope="{ row }">
      <el-button type="text" @click="assignPermission(row)">分配权限</el-button>
      <el-button type="text" @click="editRole(row)">编辑</el-button>
      <el-button type="text" @click="delRole(row.id)">删除</el-button>
    </template>
  </el-table-column>
</el-table>
```

### 8.2 分配权限（el-tree 回显）

```html
<el-tree
  ref="permTree"
  :data="permList"
  :props="{ label: 'name', children: 'children' }"
  node-key="id"
  show-checkbox
  check-strictly
  default-expand-all
/>
```

```js
// 回显已选权限
async assignPermission(row) {
  this.currentRoleId = row.id
  const { data } = await getRoleDetail(row.id)
  // ⚠️ 必须用 setCheckedKeys 而非 v-model
  this.$refs.permTree.setCheckedKeys(data.permIds)
  this.dialogVisible = true
}

// 保存分配
async savePermission() {
  const checkedKeys = this.$refs.permTree.getCheckedKeys()
  const halfCheckedKeys = this.$refs.permTree.getHalfCheckedKeys()
  await assignPerm({
    id: this.currentRoleId,
    permIds: [...checkedKeys, ...halfCheckedKeys] // 必须包含半选
  })
  this.$message.success('分配成功')
  this.dialogVisible = false
}
```

> ⚠️ **易错点**：
> - `check-strictly` 必须设为 true，否则回显时父子级联导致全选
> - 保存时必须同时提交 `getCheckedKeys()` 和 `getHalfCheckedKeys()`，否则父节点丢失

### 8.3 员工管理

```html
<el-table :data="list" border @sort-change="handleSort">
  <el-table-column label="姓名" prop="username" />
  <el-table-column label="工号" prop="workNumber" sortable="custom" />
  <el-table-column label="聘用形式" prop="formOfEmployment" :formatter="formatEmployment" />
  <el-table-column label="操作" fixed="right" width="200">
    <template slot-scope="{ row }">
      <el-button type="text" @click="$router.push(`/employee/detail/${row.id}`)">查看</el-button>
      <el-button type="text" @click="assignRole(row)">分配角色</el-button>
    </template>
  </el-table-column>
</el-table>

<!-- 分页 -->
<el-pagination
  :current-page="page.page"
  :page-size="page.size"
  :total="page.total"
  layout="total, prev, pager, next"
  @current-change="handlePageChange"
/>
```

```js
// 聘用形式枚举
const hireType = [
  { id: 1, value: '正式' },
  { id: 2, value: '非正式' }
]
function formatEmployment(row) {
  const obj = hireType.find(item => item.id === row.formOfEmployment)
  return obj ? obj.value : '未知'
}
```

### 8.4 分配角色

```js
async assignRole(employee) {
  this.userId = employee.id
  const { data } = await getEmployeeDetail(employee.id)
  // 回显：根据 roleIds 设置选中
  this.roleIds = data.roleIds
  this.dialogVisible = true
}

async saveRole() {
  await assignRoles({ id: this.userId, roleIds: this.roleIds })
  this.$message.success('分配成功')
  this.dialogVisible = false
}
```

---

## 九、文件上传与下载

### 9.1 图片上传（el-upload）

```html
<el-upload
  class="avatar-uploader"
  action="#"
  :show-file-list="false"
  :http-request="handleUpload"
  :before-upload="beforeAvatarUpload"
>
  <img v-if="imageUrl" :src="imageUrl" class="avatar">
  <i v-else class="el-icon-plus avatar-uploader-icon" />
</el-upload>
```

```js
// 上传前校验
function beforeAvatarUpload(file) {
  const isJpg = ['image/jpeg', 'image/png'].includes(file.type)
  const isLt2M = file.size / 1024 / 1024 < 2
  if (!isJpg) this.$message.error('上传头像图片只能是 JPG/PNG 格式!')
  if (!isLt2M) this.$message.error('上传头像图片大小不能超过 2MB!')
  return isJpg && isLt2M
}

// 自定义上传（配合 COS）
async handleUpload({ file }) {
  const url = await uploadToCos(file)
  this.imageUrl = url
}
```

| 方式 | 说明 |
| --- | --- |
| `action` + 默认上传 | 直接上传到服务器接口 |
| `:http-request` 覆盖 | 自定义上传逻辑（如 COS） |
| `:before-upload` | 上传前钩子，返回 false 终止 |
| `:on-success` | 上传成功回调 |
| `:on-error` | 上传失败回调 |

### 9.2 Excel 导入导出

```bash
npm i xlsx
```

```js
// 导出 Excel
import * as XLSX from 'xlsx'

export function exportExcel(data, filename = '员工列表.xlsx') {
  // 1. 数据转 sheet
  const header = { username: '姓名', mobile: '手机号', workNumber: '工号' }
  const list = data.map(item => ({
    [header.username]: item.username,
    [header.mobile]: item.mobile,
    [header.workNumber]: item.workNumber
  }))
  const sheet = XLSX.utils.json_to_sheet(list)
  // 2. 生成工作簿
  const wb = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(wb, sheet, '员工')
  // 3. 下载
  XLSX.writeFile(wb, filename)
}
```

```js
// 导入 Excel
export function readExcel(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = e => {
      const data = new Uint8Array(e.target.result)
      const wb = XLSX.read(data, { type: 'array' })
      const sheet = wb.Sheets[wb.SheetNames[0]]
      const json = XLSX.utils.sheet_to_json(sheet)
      resolve(json)
    }
    reader.onerror = reject
    reader.readAsArrayBuffer(file)
  })
}
```

> 💡 **导入流程**：用户选择文件 → FileReader 读取 → xlsx 解析 → 调用批量新增接口

### 9.3 腾讯云 COS 上传

| 优势 | 说明 |
| --- | --- |
| CDN 加速 | 全国节点加速访问 |
| 节省服务器空间 | 文件不占用应用服务器 |
| 高可用 | 三副本冗余存储 |
| 低成本 | 按量付费 |

```bash
npm i cos-js-sdk-v5
```

```js
// utils/cos.js
import Cos from 'cos-js-sdk-v5'

const cos = new Cos({
  // 临时密钥获取（后端返回）
  getAuthorization(options, callback) {
    getTempSecret().then(res => {
      callback({
        TmpSecretId: res.data.credentials.tmpSecretId,
        TmpSecretKey: res.data.credentials.tmpSecretKey,
        SecurityToken: res.data.credentials.sessionToken,
        ExpiredTime: res.data.expiredTime
      })
    })
  }
})

export function uploadToCos(file) {
  return new Promise((resolve, reject) => {
    const key = `avatar/${Date.now()}-${file.name}`
    cos.putObject({
      Bucket: 'hr-bucket-1234567890',  // 存储桶
      Region: 'ap-guangzhou',           // 地域
      Key: key,
      Body: file,
      onProgress: e => console.log(`进度: ${Math.round(e.percent * 100)}%`)
    }, (err, data) => {
      if (err) return reject(err)
      resolve(`https://${data.Location}`)
    })
  })
}
```

**COS 临时密钥获取流程：**

```
前端 → 后端 → 腾讯云 STS
        ↓
    返回临时密钥（TmpSecretId、TmpSecretKey、Token）
        ↓
前端拿到临时密钥 → 上传文件到 COS
```

> ⚠️ **易错点**：不能将永久密钥（SecretId/SecretKey）写在前端代码中，必须通过后端换取临时密钥

---

## 十、ECharts 图表

### 10.1 安装与引入

```bash
npm i echarts
```

```js
// 按需引入（推荐，减小体积）
import * as echarts from 'echarts/core'
import { LineChart, BarChart, PieChart } from 'echarts/charts'
import {
  TitleComponent, TooltipComponent, GridComponent, LegendComponent
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([
  LineChart, BarChart, PieChart,
  TitleComponent, TooltipComponent, GridComponent, LegendComponent,
  CanvasRenderer
])

export default echarts
```

### 10.2 基本使用流程

```html
<template>
  <div ref="chartRef" style="width: 600px; height: 400px"></div>
</template>

<script>
import echarts from '@/utils/echarts'
export default {
  mounted() {
    this.initChart()
  },
  methods: {
    initChart() {
      // 1. 准备 DOM 容器
      const dom = this.$refs.chartRef
      // 2. 初始化实例
      const myChart = echarts.init(dom)
      // 3. 设置配置项
      const option = {
        title: { text: '销售趋势' },
        tooltip: { trigger: 'axis' },
        xAxis: { type: 'category', data: ['1月', '2月', '3月', '4月'] },
        yAxis: { type: 'value' },
        series: [{ name: '销量', type: 'line', data: [120, 200, 150, 80] }]
      }
      myChart.setOption(option)
      // 4. 数据变化时重新 setOption
      this.myChart = myChart
    }
  }
}
</script>
```

> ⚠️ **易错点**：DOM 容器必须给定宽高，否则 echarts.init 会报警告且无法渲染

### 10.3 常用图表类型

| 类型 | type | 适用场景 |
| --- | --- | --- |
| 折线图 | `line` | 趋势变化 |
| 柱状图 | `bar` | 数值对比 |
| 饼图 | `pie` | 占比分布 |
| 散点图 | `scatter` | 关系分布 |
| 雷达图 | `radar` | 多维评估 |

```js
// 柱状图
const barOption = {
  xAxis: { type: 'category', data: ['A', 'B', 'C'] },
  yAxis: { type: 'value' },
  series: [{ type: 'bar', data: [10, 30, 20] }]
}

// 饼图
const pieOption = {
  tooltip: { trigger: 'item' },
  legend: { top: '5%', left: 'center' },
  series: [{
    type: 'pie',
    radius: ['40%', '70%'],
    data: [
      { value: 1048, name: '正式员工' },
      { value: 735, name: '试用期' },
      { value: 580, name: '外包' }
    ]
  }]
}
```

### 10.4 响应式

```js
mounted() {
  window.addEventListener('resize', this.handleResize)
},
beforeDestroy() {
  window.removeEventListener('resize', this.handleResize)
  // ⚠️ 组件销毁时务必 dispose 实例，防止内存泄漏
  this.myChart && this.myChart.dispose()
},
methods: {
  handleResize() {
    this.myChart && this.myChart.resize()
  }
}
```

> 💡 **关键三步**：初始化 → setOption → resize 监听；销毁时 dispose 释放

---

## 十一、项目部署

### 11.1 打包

```bash
# 生产环境打包
npm run build:prod

# 预发布环境打包
npm run build:stage
```

打包后生成 `dist/` 目录，包含 `index.html`、`static/`（js、css、图片等）。

### 11.2 Nginx 配置

| 功能 | 配置项 | 说明 |
| --- | --- | --- |
| 静态资源托管 | `root` / `index` | 指定 dist 目录和入口文件 |
| 反向代理 | `proxy_pass` | 转发 `/api` 到后端 |
| 路由 404 处理 | `try_files` | history 模式必备 |
| gzip 压缩 | `gzip on` | 减小传输体积 |

### 11.3 Nginx 常用配置示例

```nginx
server {
  listen 80;
  server_name localhost;

  # 静态资源托管
  location / {
    root /usr/share/nginx/html;
    index index.html;
    try_files $uri $uri/ /index.html;  # 解决路由 404
  }

  # 反向代理（解决跨域）
  location /api/ {
    proxy_pass http://backend-server/;  # 后端地址
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
  }

  # gzip 压缩
  gzip on;
  gzip_types text/plain application/javascript text/css application/json;
  gzip_min_length 1000;
}
```

> ⚠️ **易错点**：`try_files $uri $uri/ /index.html;` 这行是 history 模式部署的关键，缺失会导致刷新 404

### 11.4 历史模式 vs Hash 模式

| 对比项 | Hash 模式 | History 模式 |
| --- | --- | --- |
| URL 形式 | `http://xxx/#/home` | `http://xxx/home` |
| 是否美观 | 不美观 | 美观 |
| 是否需配置 Nginx | 不需要 | 需要 `try_files` |
| SEO | 不友好 | 友好 |
| 兼容性 | 所有浏览器 | HTML5 API |
| 刷新是否 404 | 否 | 是（未配置时） |

```js
// router/index.js
const router = new VueRouter({
  mode: 'history', // 或 'hash'（默认）
  base: process.env.VUE_APP_BASE_URL,
  routes
})
```

---

## 💡 关联面试题

**Q1：vue-element-admin 的权限控制是如何实现的？**
- 两层控制：
  - **路由级权限**：动态路由过滤，根据用户 `roles` 通过 `filterAsyncRoutes` 过滤 `asyncRoutes`，再用 `router.addRoutes()` 动态添加
  - **按钮级权限**：自定义指令 `v-permission`，根据角色移除无权限的 DOM 元素

**Q2：路由守卫 beforeEach 的逻辑是什么？**
- 1. 获取 token，无 token 则白名单放行，否则跳转登录（带 redirect 参数）
- 2. 有 token 且访问 `/login`，重定向到首页
- 3. 有 token 但无用户信息，调用 `getInfo` 获取信息并生成动态路由
- 4. `addRoutes` 后用 `next({ ...to, replace: true })` 确保新路由生效

**Q3：Vuex 中如何管理 token？为什么要同时存在 Vuex 和 Cookie？**
- Vuex 存储 token 实现响应式访问；Cookie 存储保证刷新不丢失且请求自动携带
- 单纯 Vuex 刷新会丢失；单纯 Cookie 不支持响应式

**Q4：axios 拦截器的作用？请求拦截和响应拦截分别做什么？**
- **请求拦截**：统一注入 token（Authorization 头）、设置 loading、转换数据格式
- **响应拦截**：统一错误处理（token 失效跳登录、错误提示）、脱壳 `response.data`、业务码判断

**Q5：如何处理开发环境的跨域问题？生产环境呢？**
- 开发：`vue.config.js` 配置 `devServer.proxy`，Node 服务器中转
- 生产：Nginx `proxy_pass` 反向代理，浏览器只访问同源地址

**Q6：树形结构的数据如何处理增删改查？**
- 增：传 `pid` 调接口，重新拉取数据
- 删：后端校验是否有子节点，前端不可直接递归删除
- 改：根据 `id` 更新，回显时用 `find` 递归查找节点
- 查：递归遍历 `findNode`、`treeToArr`、`arrToTree` 相互转换

**Q7：ECharts 的基本使用流程？**
- 1. 准备 DOM 容器（必须给定宽高）
- 2. `echarts.init(dom)` 初始化实例
- 3. `setOption({...})` 设置配置项
- 4. 数据变化时重新 `setOption`
- 5. 监听 `resize` 实现响应式；销毁时 `dispose` 释放

**Q8：Vue 项目如何部署到 Nginx？history 模式如何配置？**
- 打包 `npm run build:prod` 生成 dist，上传到服务器
- Nginx 配置 `root` 指向 dist 目录
- history 模式必须配置 `try_files $uri $uri/ /index.html;` 否则刷新 404

**Q9：文件上传有哪些方案？COS 对象存储的优势？**
- 方案：① 表单直接上传到服务器 ② 自定义上传到 COS ③ Base64 内嵌（小图片）
- COS 优势：CDN 加速、节省服务器空间、高可用三副本、按量付费、适合大文件

**Q10：动态路由的实现原理？**
- 路由分两部分：`constantRoutes`（静态）+ `asyncRoutes`（异步）
- 登录后获取用户 `roles`，通过 `filterAsyncRoutes` 递归过滤 `asyncRoutes` 中匹配角色的路由
- 用 `router.addRoutes()` 动态注入，配合 `next({ ...to, replace: true })` 确保生效
