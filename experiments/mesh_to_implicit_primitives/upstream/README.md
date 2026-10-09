# RSIAgent 适配补丁

上游仓库：https://github.com/AetherLabsAI/RSIAgent

适配代码保存于用户自己的仓库：
https://github.com/CAN-Lee/Intern_SUSTech/tree/thirdparty/rsiagent-mesh 。
主仓库以 `submodule/RSIAgent` gitlink 固定该分支中的提交；上游仓库没有被修改。

基准提交：`4d7ef43770dda341fccd9a5743db92407687c615`。
`mesh-domain.patch` 记录此实现对上游的修改，当前工作区已经应用，无需再次执行。
在该提交的干净 checkout 中可用 `git apply mesh-domain.patch` 重建修改。

- `llm/client.py`：通过显式 `RSI_LLM_MODE=openai` 使用配置的 Gateway，保留默认 OpenRouter 路径；记录返回的 token 用量。
- `core/loop.py`：显式 fail-fast 模式关闭无限等待服务恢复，默认行为不变。
- `explore/phase1_wave.py`：增加可选几何领域回调；并发调度、验证屏障和顺序提交仍在原函数中执行。

完整项目运行记录会额外保存实际 revision、实际 diff 与其哈希，不能仅凭此补丁文件推断某次运行的版本。
