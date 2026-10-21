package com.safety.admin.modeltask;

import com.safety.admin.common.BusinessException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import jakarta.annotation.PreDestroy;
import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.nio.charset.Charset;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * 模型在线训练任务：异步调用算法域的真实 YOLOv8 训练脚本
 * （scripts/train_yolo.py），演示级配置（小数据集 + 1 epoch），
 * 训练完成后从 Ultralytics results.csv 提取最终轮真实指标。
 */
@Service
public class ModelTrainService {

    private static final Logger log = LoggerFactory.getLogger(ModelTrainService.class);
    private static final Pattern CSV_LINE = Pattern.compile("^\\s*(\\d+),(.+)$");

    private final ModelTrainTaskRepository repository;
    private final ExecutorService executor = Executors.newSingleThreadExecutor();

    private final String repoRoot;
    private final String python;
    private final String dataYaml;
    private final String baseModel;
    private final int epochs;

    public ModelTrainService(ModelTrainTaskRepository repository,
                             @Value("${app.train.repo-root}") String repoRoot,
                             @Value("${app.train.python}") String python,
                             @Value("${app.train.data-yaml}") String dataYaml,
                             @Value("${app.train.base-model}") String baseModel,
                             @Value("${app.train.epochs}") int epochs) {
        this.repository = repository;
        this.repoRoot = Path.of(repoRoot).toAbsolutePath().normalize().toString();
        this.python = python;
        this.dataYaml = dataYaml;
        this.baseModel = baseModel;
        this.epochs = epochs;
    }

    public ModelTrainTask create(String name, String datasetTag) {
        ModelTrainTask task = new ModelTrainTask();
        task.setName(name != null && !name.isBlank() ? name : "admin-smoke-" + System.currentTimeMillis());
        task.setDatasetTag(datasetTag);
        task.setEpochs(epochs);
        task = repository.save(task);
        ModelTrainTask saved = task;
        executor.submit(() -> run(saved.getId()));
        return saved;
    }

    public ModelTrainTask get(Long id) {
        return repository.findById(id).orElseThrow(() -> new BusinessException(404, "训练任务不存在"));
    }

    public List<ModelTrainTask> list() {
        return repository.findAll();
    }

    /** 最近一次已完成的训练指标；无则抛 404。 */
    public ModelTrainTask latestEvaluation() {
        return repository.findTopByOrderByIdDesc()
                .filter(t -> t.getStatus().equals("completed"))
                .orElseThrow(() -> new BusinessException(404, "暂无已完成的训练评估结果"));
    }

    private void run(Long taskId) {
        ModelTrainTask task = repository.findById(taskId).orElse(null);
        if (task == null) {
            return;
        }
        String runName = "admin-" + task.getId() + "-" + System.currentTimeMillis();
        Path logFile = Path.of(repoRoot, "backend-java", "logs", "train-" + task.getId() + ".log");
        task.setStatus("running");
        task.setLogPath(logFile.toString());
        repository.save(task);
        log.info("训练任务 {} 启动：{}", task.getId(), task.getName());
        try {
            Files.createDirectories(logFile.getParent());
            List<String> command = List.of(
                    Path.of(repoRoot, ".venv", "Scripts", "python.exe").toString(),
                    "scripts/train_yolo.py",
                    "--data", dataYaml,
                    "--model", baseModel,
                    "--epochs", String.valueOf(task.getEpochs()),
                    "--workers", "0",
                    "--name", runName);
            ProcessBuilder builder = new ProcessBuilder(command);
            builder.directory(Path.of(repoRoot).toFile());
            builder.redirectErrorStream(true);
            Process process = builder.start();
            List<String> output = new ArrayList<>();
            try (BufferedReader reader = new BufferedReader(
                    new InputStreamReader(process.getInputStream(), Charset.forName("GB18030")))) {
                String line;
                while ((line = reader.readLine()) != null) {
                    output.add(line);
                    if (output.size() <= 400) {
                        Files.write(logFile, output);
                    }
                }
            }
            int exit = process.waitFor();
            Files.writeString(logFile, String.join(System.lineSeparator(), output));
            if (exit != 0) {
                task.setStatus("failed");
                task.setErrorMessage("训练脚本退出码 " + exit + "，详见日志");
                task.setFinishedAt(LocalDateTime.now());
                repository.save(task);
                return;
            }
            applyTrainingOutputs(task, runName, output);
        } catch (IOException exc) {
            task.setStatus("failed");
            task.setErrorMessage("训练进程启动失败：" + exc.getMessage());
            task.setFinishedAt(LocalDateTime.now());
            repository.save(task);
        } catch (InterruptedException exc) {
            Thread.currentThread().interrupt();
            task.setStatus("failed");
            task.setErrorMessage("训练被中断");
            repository.save(task);
        }
    }

    /** 从 Ultralytics runs 目录与输出日志中提取真实产物路径与最终轮指标。 */
    private void applyTrainingOutputs(ModelTrainTask task, String runName, List<String> output) {
        Path runsDir = Path.of(repoRoot, "runs", "train", runName);
        Path resultsCsv = runsDir.resolve("results.csv");
        task.setRunDir(runsDir.toString());
        Path best = runsDir.resolve("weights").resolve("best.pt");
        task.setBestWeights(Files.exists(best) ? best.toString() : null);
        if (Files.exists(resultsCsv)) {
            task.setMetricsJson(extractFinalMetrics(resultsCsv));
        } else {
            // 训练输出没有 results.csv 时从日志尾部兜底提取摘要
            task.setMetricsJson("{\"source\": \"console\", \"tail\": \"" +
                    String.join(" ", output.subList(Math.max(0, output.size() - 5), output.size()))
                            .replace("\"", "'").substring(0, Math.min(400, Math.min(5, output.size()) >= output.size() ? 0 : 400)) + "\"}");
        }
        task.setStatus("completed");
        task.setFinishedAt(LocalDateTime.now());
        repository.save(task);
        log.info("训练任务 {} 完成", task.getId());
    }

    /** 解析 results.csv 最后一行：epoch, train/box_loss, ..., metrics/precision(B), metrics/recall(B), metrics/mAP50(B), metrics/mAP50-95(B), ... */
    private String extractFinalMetrics(Path csv) {
        try {
            List<String> lines = Files.readAllLines(csv);
            if (lines.size() < 2) {
                return "{\"source\": \"results.csv\", \"note\": \"无数据行\"}";
            }
            String[] header = stripSpaces(lines.get(0)).split(",");
            String[] last = stripSpaces(lines.get(lines.size() - 1)).split(",");
            StringBuilder json = new StringBuilder("{\"source\": \"results.csv\", \"final_epoch\": ");
            json.append(last[0].trim());
            for (int i = 0; i < header.length && i < last.length; i++) {
                String column = header[i].trim();
                Matcher matcher = Pattern.compile("metrics/(\\w+)\\((\\w+)\\)").matcher(column);
                if (matcher.matches()) {
                    json.append(", \\\"").append(matcher.group(1)).append("\\\": ").append(last[i].trim());
                }
            }
            json.append("}");
            return json.toString().replace("\\\"", "\"");
        } catch (IOException exc) {
            return "{\"source\": \"results.csv\", \"error\": \"" + exc.getMessage() + "\"}";
        }
    }

    private String stripSpaces(String line) {
        // Ultralytics results.csv 表头自带对齐空格（如 "                  epoch"）
        return line.replaceAll("(^|,)\\s+", "$1").replaceAll("\\s+(,|$)", "$1");
    }

    @PreDestroy
    public void shutdown() {
        executor.shutdownNow();
    }
}
