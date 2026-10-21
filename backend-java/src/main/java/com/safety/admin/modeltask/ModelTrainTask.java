package com.safety.admin.modeltask;

import jakarta.persistence.*;
import java.time.LocalDateTime;

@Entity
@Table(name = "model_train_tasks")
public class ModelTrainTask {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, length = 120)
    private String name;

    /** pending / running / completed / failed */
    @Column(nullable = false, length = 20)
    private String status = "pending";

    @Column(length = 100)
    private String datasetTag;

    private int epochs;

    @Column(length = 300)
    private String runDir;

    @Column(length = 300)
    private String bestWeights;

    /** 训练完成后从 results.csv 提取的最终轮真实指标（JSON 文本） */
    @Column(length = 1000)
    private String metricsJson;

    @Column(length = 300)
    private String logPath;

    @Column(length = 500)
    private String errorMessage;

    @Column(nullable = false)
    private LocalDateTime createdAt = LocalDateTime.now();

    private LocalDateTime finishedAt;

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    public String getName() { return name; }
    public void setName(String name) { this.name = name; }
    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
    public String getDatasetTag() { return datasetTag; }
    public void setDatasetTag(String datasetTag) { this.datasetTag = datasetTag; }
    public int getEpochs() { return epochs; }
    public void setEpochs(int epochs) { this.epochs = epochs; }
    public String getRunDir() { return runDir; }
    public void setRunDir(String runDir) { this.runDir = runDir; }
    public String getBestWeights() { return bestWeights; }
    public void setBestWeights(String bestWeights) { this.bestWeights = bestWeights; }
    public String getMetricsJson() { return metricsJson; }
    public void setMetricsJson(String metricsJson) { this.metricsJson = metricsJson; }
    public String getLogPath() { return logPath; }
    public void setLogPath(String logPath) { this.logPath = logPath; }
    public String getErrorMessage() { return errorMessage; }
    public void setErrorMessage(String errorMessage) { this.errorMessage = errorMessage; }
    public LocalDateTime getCreatedAt() { return createdAt; }
    public void setCreatedAt(LocalDateTime createdAt) { this.createdAt = createdAt; }
    public LocalDateTime getFinishedAt() { return finishedAt; }
    public void setFinishedAt(LocalDateTime finishedAt) { this.finishedAt = finishedAt; }
}
