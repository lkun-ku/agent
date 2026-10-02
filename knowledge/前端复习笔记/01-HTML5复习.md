# HTML5 复习

> HTML（HyperText Markup Language）是构建网页结构的标记语言，HTML5 是其最新版本，新增了语义标签、媒体标签、表单控件等特性。

## 一、HTML 基础结构

### 1.1 文档基本骨架

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>页面标题</title>
</head>
<body>
  <!-- 页面内容 -->
</body>
</html>
```

- `<!DOCTYPE html>`：声明文档类型为 HTML5
- `<html lang="zh-CN">`：根标签，`lang` 属性指定语言
- `<head>`：头部信息，包含字符集、视口、标题等元数据
- `<body>`：页面主体内容

### 1.2 标签关系

- **嵌套关系**（父子）：`<html>` 包含 `<head>` 和 `<body>`
- **并列关系**（兄弟）：`<head>` 与 `<body>` 并列

---

## 二、文本与语义标签

### 2.1 标题与段落

| 标签 | 说明 |
| --- | --- |
| `<h1>` ~ `<h6>` | 标题标签，`h1` 权重最高，一个页面建议只有一个 `h1` |
| `<p>` | 段落标签 |
| `<br>` | 换行（单标签） |
| `<hr>` | 水平分割线 |

### 2.2 强调与重要性

| 标签 | 说明 | 语义 |
| --- | --- | --- |
| `<strong>` | 加粗 | 强调内容的重要性 |
| `<em>` | 斜体 | 强调内容的语气 |
| `<b>` | 加粗 | 无语义，仅视觉效果 |
| `<i>` | 斜体 | 无语义，仅视觉效果 |

### 2.3 HTML5 语义化标签

```html
<header>   <!-- 页头 -->
<nav>      <!-- 导航 -->
<main>     <!-- 主内容 -->
<article>  <!-- 独立文章 -->
<section>  <!-- 内容区块 -->
<aside>    <!-- 侧边栏 -->
<footer>   <!-- 页脚 -->
<figure>   <!-- 图文组合 -->
<figcaption> <!-- 图文标题 -->
```

**语义化的好处：**
1. 提升代码可读性，便于团队协作
2. 利于 SEO（搜索引擎优化）
3. 方便屏幕阅读器等辅助设备解析

---

## 三、媒体标签

### 3.1 图像标签

```html
<img src="图片路径" alt="替代文本" title="鼠标悬停提示" width="200">
```

| 属性 | 说明 |
| --- | --- |
| `src` | 图片路径（必需） |
| `alt` | 图片加载失败时的替代文本（必需，利于 SEO） |
| `title` | 鼠标悬停时的提示文字 |
| `width`/`height` | 宽高（建议只设一个，保持等比缩放） |

### 3.2 音视频标签（HTML5 新增）

```html
<!-- 音频 -->
<audio src="music.mp3" controls autoplay loop muted></audio>

<!-- 视频 -->
<video src="video.mp4" controls poster="封面.jpg" width="640"></video>
```

| 属性 | 说明 |
| --- | --- |
| `controls` | 显示播放控件 |
| `autoplay` | 自动播放（多数浏览器需配合 `muted`） |
| `loop` | 循环播放 |
| `muted` | 静音 |
| `poster` | 视频封面图（仅 video） |

### 3.3 新增图片格式

| 格式 | 特点 |
| --- | --- |
| WebP | 体积更小，支持透明，兼容性好 |
| AVIF | 压缩率更高，较新格式 |
| GIF | 支持动画，体积较大 |

---

## 四、链接标签

```html
<!-- 外部链接 -->
<a href="https://www.baidu.com" target="_blank">百度</a>

<!-- 内部链接 -->
<a href="./about.html">关于我们</a>

<!-- 锚点链接（页面内跳转） -->
<a href="#section1">跳转到第一节</a>
<h2 id="section1">第一节</h2>

<!-- 下载链接 -->
<a href="file.zip" download>下载文件</a>
```

| `target` 值 | 说明 |
| --- | --- |
| `_self` | 当前窗口打开（默认） |
| `_blank` | 新窗口打开 |

---

## 五、列表标签

### 5.1 无序列表

```html
<ul>
  <li>列表项1</li>
  <li>列表项2</li>
</ul>
```

### 5.2 有序列表

```html
<ol type="1" start="1">
  <li>第一项</li>
  <li>第二项</li>
</ol>
```

`type` 属性：`1`（数字）、`a`（小写字母）、`A`（大写字母）、`i`（小写罗马）、`I`（大写罗马）

### 5.3 自定义列表

```html
<dl>
  <dt>术语</dt>
  <dd>描述内容</dd>
</dl>
```

---

## 六、表格标签

```html
<table border="1">
  <thead>
    <tr>
      <th>姓名</th>
      <th>年龄</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>张三</td>
      <td>18</td>
    </tr>
  </tbody>
</table>
```

| 标签 | 说明 |
| --- | --- |
| `<table>` | 表格容器 |
| `<thead>`/`<tbody>`/`<tfoot>` | 表头/表体/表尾（语义化分组） |
| `<tr>` | 行 |
| `<th>` | 表头单元格（加粗居中） |
| `<td>` | 标准单元格 |

### 合并单元格

| 属性 | 说明 |
| --- | --- |
| `colspan="n"` | 跨列合并（水平合并 n 列） |
| `rowspan="n"` | 跨行合并（垂直合并 n 行） |

> ⚠️ 合并后需删除被合并的单元格

---

## 七、表单（重点）

### 7.1 表单容器

```html
<form action="提交地址" method="POST">
  <!-- 表单控件 -->
</form>
```

| 属性 | 说明 |
| --- | --- |
| `action` | 数据提交的目标 URL |
| `method` | 提交方式：`GET`（默认）/ `POST` |

### 7.2 input 输入控件

| `type` 值 | 说明 |
| --- | --- |
| `text` | 单行文本框 |
| `password` | 密码框（输入内容显示为圆点） |
| `radio` | 单选框（同 `name` 分为一组） |
| `checkbox` | 复选框 |
| `file` | 文件上传 |
| `email` | 邮箱（带格式校验） |
| `number` | 数字 |
| `date` | 日期选择 |
| `color` | 颜色选择 |
| `range` | 滑块 |
| `submit` | 提交按钮 |
| `reset` | 重置按钮 |
| `button` | 普通按钮 |

**常用属性：**

| 属性 | 说明 |
| --- | --- |
| `placeholder` | 占位提示文字 |
| `value` | 默认值 |
| `name` | 提交数据的字段名 |
| `checked` | 默认选中（radio/checkbox） |
| `disabled` | 禁用 |
| `maxlength` | 最大输入长度 |
| `multiple` | 允许多选（file） |
| `autocomplete` | 自动填充（`on`/`off`） |

### 7.3 其他表单控件

```html
<!-- 下拉选择 -->
<select name="city">
  <option value="bj">北京</option>
  <option value="sh" selected>上海</option>
</select>

<!-- 文本域 -->
<textarea name="msg" cols="30" rows="10" placeholder="请输入留言"></textarea>

<!-- 按钮 -->
<button type="submit">提交</button>
<button type="button">普通按钮</button>
```

### 7.4 label 标签

关联文字与表单控件，扩大点击区域：

```html
<!-- 方式一：for + id -->
<input type="radio" id="male">
<label for="male">男</label>

<!-- 方式二：包裹 -->
<label>
  <input type="checkbox"> 同意协议
</label>
```

---

## 八、路径

| 路径类型 | 写法 | 说明 |
| --- | --- | --- |
| 绝对路径 | `https://...` 或 `C:/...` | 完整地址 |
| 同级路径 | `./文件名` 或 `文件名` | 同一目录 |
| 下级路径 | `./目录/文件名` | 进入子目录 |
| 上级路径 | `../文件名` | 返回上一级 |

---

## 九、特殊字符

| 字符 | 实体 | 说明 |
| --- | --- | --- |
| 空格 | `&nbsp;` | 连续空格 |
| `<` | `&lt;` | 小于号 |
| `>` | `&gt;` | 大于号 |
| `&` | `&amp;` | 与符号 |
| `©` | `&copy;` | 版权符号 |

---

## 💡 关联面试题

**Q1：说说 HTML 语义化的理解？**
- 用正确的标签做正确的事，如标题用 `h1`~`h6`、导航用 `nav`、文章用 `article`
- 好处：① 提升代码可读性和可维护性 ② 利于 SEO ③ 方便辅助设备（如屏幕阅读器）解析

**Q2：img 标签的 title 和 alt 有什么区别？**
- `alt`：图片加载失败时的替代文本，是必需属性，利于 SEO 和无障碍访问
- `title`：鼠标悬停时的提示文字，可选

**Q3：GET 和 POST 的区别？**
- `GET`：参数拼接在 URL 后，有长度限制，会被缓存，不适合敏感数据
- `POST`：参数在请求体中，无长度限制，不会缓存，相对安全
