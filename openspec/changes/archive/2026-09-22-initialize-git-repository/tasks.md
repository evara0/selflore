## 1. 基线文件与初始化

- [x] 1.1 创建简洁的 `README.md`，仅描述 SelfLore 项目基本信息，并通过人工审查确认不包含未批准的设计范围
- [x] 1.2 创建根目录 `.gitignore`，忽略 `docs/`、`.agents/` 及常见敏感和生成文件，并使用 `git check-ignore` 验证本地目录被忽略而 `openspec/` 未被忽略
- [x] 1.3 在 `G:\selflore` 初始化 Git 仓库且不配置 remote，并用 `git rev-parse --show-toplevel` 与 `git remote -v` 验证本地工作树和无远程地址状态

## 2. 受控基线提交

- [x] 2.1 显式暂存 `.gitignore`、`README.md` 与 `openspec/`，检查暂存文件清单、大小和常见凭据模式，确认未暂存 `docs/`、`.agents/` 或疑似敏感文件
- [x] 2.2 创建初始本地提交，并用 `git show --stat --oneline HEAD`、`git status --short` 和 `git remote -v` 验证提交范围、干净工作树及未创建远程连接
