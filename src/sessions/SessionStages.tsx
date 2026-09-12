import { CheckCircle2, Circle, CircleAlert, Wrench } from "lucide-react";
import type { SessionHistory, SessionStatus } from "./types";
import { toolStages } from "./stages";

const phase: Record<SessionStatus, { kind: string; title: string; detail: string }> = {
  ready: { kind: "progress", title: "等待开始", detail: "尚未开始执行，保存消息不代表任务已完成。" },
  running: { kind: "progress", title: "执行中", detail: "显示最近读取的执行状态，不代表实时推送。" },
  waiting_input: { kind: "progress", title: "等待补充输入", detail: "请查看上方消息中的说明。" },
  completed: { kind: "result", title: "会话已完成", detail: "具体任务内容请查看左侧 Todo；此会话只读。" },
  failed: { kind: "error", title: "执行失败", detail: "历史已保留，可查看工具错误或尝试重试。" },
  cancelled: { kind: "progress", title: "执行已停止", detail: "取消不是错误，历史记录已保留。" },
};
const toolLabels = { started: "已开始", completed: "已完成", failed: "失败", cancelled: "已停止", unfinished: "未记录结束状态" };

export function SessionStages({ history }: { history: SessionHistory }) {
  const current = phase[history.status];
  const stages = toolStages(history);
  const Icon = current.kind === "error" ? CircleAlert : current.kind === "result" ? CheckCircle2 : Circle;
  return <section aria-label="执行阶段" className="mt-4 space-y-3 border-t border-[var(--theme-border-normal)] pt-4">
    <h4 className="text-xs text-[var(--theme-text-secondary)]">执行阶段 · 历史快照</h4>
    <div data-stage={current.kind} className={`rounded-lg border p-3 ${current.kind === "error" ? "border-[var(--theme-status-error)] text-[var(--theme-status-error)]" : current.kind === "result" ? "border-[var(--theme-status-success)] text-[var(--theme-status-success)]" : "border-[var(--theme-border-normal)] text-[var(--theme-text-secondary)]"}`}>
      <p className="flex items-center gap-2"><Icon aria-hidden="true" className="size-4 shrink-0" />{current.title}</p>
      <p className="mt-1 text-xs text-[var(--theme-text-secondary)]">{current.detail}</p>
    </div>
    {stages.length > 0 && <ol aria-label="工具阶段" className="space-y-2">
      {stages.map((stage) => <li key={stage.key} data-stage="tool" className="rounded-lg bg-[var(--theme-chat-message-background)] p-3">
        <div className="flex items-start gap-2">
          <Wrench aria-hidden="true" className="mt-1 size-3.5 shrink-0" />
          <span className="min-w-0 flex-1 break-words [overflow-wrap:anywhere]">{stage.tool}</span>
          <span className={`shrink-0 text-xs ${stage.state === "failed" ? "text-[var(--theme-status-error)]" : "text-[var(--theme-text-secondary)]"}`}>{toolLabels[stage.state]}</span>
        </div>
        <p className="mt-1 text-xs text-[var(--theme-text-muted)]">执行记录 {stage.run}</p>
        {stage.summary && <p className="mt-2 whitespace-pre-wrap break-words text-xs [overflow-wrap:anywhere]">{stage.summary}</p>}
        {stage.state === "failed" && !stage.summary && <p className="mt-2 text-xs text-[var(--theme-status-error)]">工具执行失败，未记录可展示的错误说明。</p>}
      </li>)}
    </ol>}
    <p className="text-xs text-[var(--theme-text-muted)]">重新点击历史会话可刷新记录；工具完成不等于 Todo 已提交。</p>
  </section>;
}
