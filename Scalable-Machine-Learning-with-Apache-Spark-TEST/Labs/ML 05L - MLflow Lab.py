# Databricks notebook source
# MAGIC %md-sandbox
# MAGIC 
# MAGIC <div style="text-align: center; line-height: 0; padding-top: 9px;">
# MAGIC   <img src="https://databricks.com/wp-content/uploads/2018/03/db-academy-rgb-1200px.png" alt="Databricks Learning" style="width: 600px">
# MAGIC </div>

# COMMAND ----------

# MAGIC %md # MLflow Lab
# MAGIC 
# MAGIC In this lab we will explore the path to moving models to production with MLflow using the following steps:
# MAGIC 
# MAGIC 1. Load in Airbnb dataset, and save both training dataset and test dataset as Delta tables
# MAGIC 2. Train an MLlib linear regression model using all the listing features and tracking parameters, metrics artifacts and Delta table version to MLflow
# MAGIC 3. Register this initial model and move it to staging using MLflow Model Registry
# MAGIC 4. Add a new column, `log_price` to both our train and test table and update the corresponding Delta tables
# MAGIC 5. Train a second MLlib linear regression model, this time using `log_price` as our target and training on all features, tracking to MLflow 
# MAGIC 6. Compare the performance of the different runs by looking at the underlying data versions for both models
# MAGIC 7. Move the better performing model to production in MLflow model registry
# MAGIC 
# MAGIC ## ![Spark Logo Tiny](https://files.training.databricks.com/images/105/logo_spark_tiny.png) In this lab you:<br>
# MAGIC - Create Delta tables
# MAGIC - Track your MLlib model and Delta table version using MLflow
# MAGIC - Use MLflow model registry to version your models

# COMMAND ----------

# MAGIC %run "../Includes/Classroom-Setup"

# COMMAND ----------

# MAGIC %md
# MAGIC 
# MAGIC ###  Step 1. Creating Delta Tables

# COMMAND ----------

# MAGIC %md 
# MAGIC 
# MAGIC Data versioning is an advantage of using Delta Lake, which preserves previous versions of datasets so that you can restore later.
# MAGIC 
# MAGIC Let's split our dataset into train and test datasets, and writing them out in Delta format. You can read more at the Delta Lake [documentation](https://docs.delta.io/latest/index.html).

# COMMAND ----------

filePath = f"{datasets_dir}/airbnb/sf-listings/sf-listings-2019-03-06-clean.delta/"
airbnbDF = spark.read.format("delta").load(filePath)

trainDF, testDF = airbnbDF.randomSplit([.8, .2], seed=42)

# COMMAND ----------

trainDeltaPath = userhome + "/machine-learning-p/train.delta"
testDeltaPath = userhome + "/machine-learning-p/test.delta"

# In case paths already exists
dbutils.fs.rm(trainDeltaPath, True)
dbutils.fs.rm(testDeltaPath, True)

(trainDF
  .write
  .mode("overwrite")
  .format("delta")
  .save(trainDeltaPath)
)

(testDF
  .write
  .mode("overwrite")
  .format("delta")
  .save(testDeltaPath)
)

# COMMAND ----------

# MAGIC %md
# MAGIC 
# MAGIC Let's now read in our train and test Delta tables, specifying that we want the first version of these tables. This [blog post](https://databricks.com/blog/2019/02/04/introducing-delta-time-travel-for-large-scale-data-lakes.html) has a great example of how to read in a Delta table at a given version.

# COMMAND ----------

# TODO
data_version = 0
trainDelta = <FILL_IN>
testDelta = <FILL_IN>

# COMMAND ----------

# MAGIC %md
# MAGIC ### Review Delta Table History
# MAGIC All the transactions for this table are stored within this table including the initial set of insertions, update, delete, merge, and inserts.

# COMMAND ----------

display(spark.sql(f"DESCRIBE HISTORY delta.`{trainDeltaPath}`"))

# COMMAND ----------

# MAGIC %md
# MAGIC 
# MAGIC By default Delta tables [keep a commit history of 30 days](https://docs.databricks.com/delta/delta-batch.html#data-retention). This retention period can be adjusted by setting `delta.logRetentionDuration`, which will determine how far back in time you can go. Note that setting this can result in storage costs to go up. 
# MAGIC 
# MAGIC <img src="https://files.training.databricks.com/images/icon_note_24.png"/> Be aware that versioning with Delta in this manner may not be feasible as a long term solution. The retention period of Delta tables can be increased, but with that comes additional costs to storage. Alternative methods of data versioning when training models and tracking to MLflow is to save copies of the datasets, either as an MLflow artifact (for a small dataset), or save to a separate distributed location and record the location of the underlying dataset as a tag in MLflow

# COMMAND ----------

# MAGIC %md
# MAGIC 
# MAGIC ### Step 2. Log initial run to MLflow
# MAGIC 
# MAGIC Let's first log a run to MLflow where we use all features. We use the same approach with RFormula as before. This time however, let's also log both the version of our data and the data path to MLflow. 

# COMMAND ----------

# TODO
import mlflow
import mlflow.spark
from pyspark.ml.regression import LinearRegression
from pyspark.ml import Pipeline
from pyspark.ml.evaluation import RegressionEvaluator
from pyspark.ml.feature import RFormula

with mlflow.start_run(run_name="lr_model") as run:
  
  # Log parameters
  mlflow.log_param("data_path", trainDeltaPath)  
  # TODO: Log label: price-all-features
  # TODO: Log data_version: data_version
  
    
  # Create pipeline
  rFormula = RFormula(formula="price ~ .", featuresCol="features", labelCol="price", handleInvalid="skip")
  lr = LinearRegression(labelCol="price", featuresCol="features")
  pipeline = Pipeline(stages = [rFormula, lr])
  model = pipeline.fit(trainDelta)
  
  # Log pipeline
  # TODO: Log model: model

  # Create predictions and metrics
  predDF = model.transform(testDelta)
  regressionEvaluator = RegressionEvaluator(labelCol="price", predictionCol="prediction")
  rmse = regressionEvaluator.setMetricName("rmse").evaluate(predDF)
  r2 = regressionEvaluator.setMetricName("r2").evaluate(predDF)
  
  # Log metrics
  # TODO: Log RMSE
  # TODO: Log R2
  
  runID = run.info.run_id

# COMMAND ----------

# MAGIC %md 
# MAGIC 
# MAGIC ### Step 3. Register model and move to staging using MLflow Model Registry
# MAGIC 
# MAGIC We are happy with the performance of the above model and want to move it to staging. Let's create the model and register it to the MLflow model registry.
# MAGIC 
# MAGIC <img src="https://files.training.databricks.com/images/icon_note_24.png"/> Make sure the path to `model_uri` matches the subdirectory (the second argument to `mlflow.log_model()`) included above.

# COMMAND ----------

model_name = f"{cleaned_username}_mllib_lr"
model_uri = f"runs:/{runID}/model"

model_details = mlflow.register_model(model_uri=model_uri, name=model_name)

# COMMAND ----------

# MAGIC %md
# MAGIC 
# MAGIC Transition model to staging.

# COMMAND ----------

from mlflow.tracking.client import MlflowClient

client = MlflowClient()

client.transition_model_version_stage(
  name=model_name,
  version=1,
  stage="Staging"
)

# COMMAND ----------

# MAGIC %md
# MAGIC 
# MAGIC Add a model description using [update_registered_model](https://mlflow.org/docs/latest/python_api/mlflow.tracking.html#mlflow.tracking.MlflowClient.update_registered_model).

# COMMAND ----------

# TODO
client.update_registered_model(
  <FILL_IN>
)

# COMMAND ----------

# MAGIC %md
# MAGIC 
# MAGIC ###  Step 4. Feature Engineering: Evolve Data Schema
# MAGIC 
# MAGIC We now want to do some feature engineering with the aim of improving model performance; we can use Delta Lake to track older versions of the dataset. 
# MAGIC 
# MAGIC We will add `log_price` as a new column and update our Delta table with it.

# COMMAND ----------

from pyspark.sql.functions import col, log, exp

# Create a new log_price column for both train and test datasets
trainNew = trainDelta.withColumn("log_price", log(col("price")))
testNew = testDelta.withColumn("log_price", log(col("price")))

# COMMAND ----------

# MAGIC %md 
# MAGIC Save the updated DataFrames to `trainDeltaPath` and `testDeltaPath`, respectively, passing the `mergeSchema` option to safely evolve its schema.

# COMMAND ----------

# TODO
trainNew.write.<FILL_IN>
testNew.write.<FILL_IN>

# COMMAND ----------

# MAGIC %md
# MAGIC 
# MAGIC Look at the difference between the original & modified schemas

# COMMAND ----------

set(trainNew.schema.fields) ^ set(trainDelta.schema.fields)

# COMMAND ----------

# MAGIC %md 
# MAGIC 
# MAGIC Let's review the Delta history of our `train_delta` table and load in the most recent versions of our train and test Delta tables.

# COMMAND ----------

display(spark.sql(f"DESCRIBE HISTORY delta.`{trainDeltaPath}`"))

# COMMAND ----------

data_version = 1
trainDeltaNew = spark.read.format("delta").option("versionAsOf", data_version).load(trainDeltaPath)  
testDeltaNew = spark.read.format("delta").option("versionAsOf", data_version).load(testDeltaPath)

# COMMAND ----------

# MAGIC %md
# MAGIC 
# MAGIC ### Step 5. Use `log_price` as target and track run with MLflow
# MAGIC 
# MAGIC Retrain the model on the updated data and compare its performance to the original, logging results to MLflow.

# COMMAND ----------

with mlflow.start_run(run_name="lr_log_model") as run:
  
  # Log parameters
  mlflow.log_param("label", "log-price")
  mlflow.log_param("data_version", data_version)
  mlflow.log_param("data_path", trainDeltaPath)    
 
  # Create pipeline
  rFormula = RFormula(formula="log_price ~ . - price", featuresCol="features", labelCol="log_price", handleInvalid="skip")  
  lr = LinearRegression(labelCol="log_price", predictionCol="log_prediction")
  pipeline = Pipeline(stages = [rFormula, lr])
  pipelineModel = pipeline.fit(trainDeltaNew)
   
  # Log model and update the registered model
  mlflow.spark.log_model(
    spark_model=pipelineModel,
    artifact_path="log-model",
    registered_model_name=model_name,
  )  
  
  # Create predictions and metrics
  predDF = pipelineModel.transform(testDelta)
  expDF = predDF.withColumn("prediction", exp(col("log_prediction")))
  rmse = regressionEvaluator.setMetricName("rmse").evaluate(expDF)
  r2 = regressionEvaluator.setMetricName("r2").evaluate(expDF)
  
  # Log metrics
  mlflow.log_metric("rmse", rmse)
  mlflow.log_metric("r2", r2)  
  
  runID = run.info.run_id

# COMMAND ----------

# MAGIC %md
# MAGIC 
# MAGIC ### Step 6. Compare performance across runs by looking at Delta table versions 
# MAGIC 
# MAGIC Use MLflow's [`mlflow.search_runs`](https://mlflow.org/docs/latest/python_api/mlflow.html#mlflow.search_runs) API to identify runs according to the version of data the run was trained on. Let's compare our runs according to our data versions.
# MAGIC 
# MAGIC Filter based on `params.data_path` and `params.data_version`.

# COMMAND ----------

# TODO
data_version = 0

mlflow.search_runs(<FILL_IN>)

# COMMAND ----------

# TODO
data_version = 1

mlflow.search_runs(<FILL_IN>)

# COMMAND ----------

# MAGIC %md
# MAGIC 
# MAGIC Which version of the data produced the best model?

# COMMAND ----------

# MAGIC %md
# MAGIC 
# MAGIC ### Step 7. Move best performing model to production using MLflow model registry
# MAGIC 
# MAGIC Get the most recent model version and move it to production.

# COMMAND ----------

model_version_infos = client.search_model_versions(f"name = '{model_name}'")
new_model_version = max([model_version_info.version for model_version_info in model_version_infos])

# COMMAND ----------

client.update_model_version(
  name=model_name,
  version=new_model_version,
  description="This model version was built using a MLlib Linear Regression model with all features and log_price as predictor."
)

# COMMAND ----------

model_version_details = client.get_model_version(name=model_name, version=new_model_version)
model_version_details.status

# COMMAND ----------

# TODO
# Move Model into Production
client.transition_model_version_stage(
  <FILL_IN>
)

# COMMAND ----------

# MAGIC %md 
# MAGIC 
# MAGIC Have a look at the MLflow model registry UI to check that your models have been successfully registered. You should see that version 1 of your model is now in staging, with version 2 in production.

# COMMAND ----------

# MAGIC %md
# MAGIC 
# MAGIC To finish the lab, let's clean up by archiving both model versions and deleting the whole model from the registry

# COMMAND ----------

client.transition_model_version_stage(
  name=model_name,
  version=1,
  stage="Archived"
)

# COMMAND ----------

client.transition_model_version_stage(
  name=model_name,
  version=2,
  stage="Archived"
)

# COMMAND ----------

client.delete_registered_model(model_name)

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC &copy; 2021 Databricks, Inc. All rights reserved.<br/>
# MAGIC Apache, Apache Spark, Spark and the Spark logo are trademarks of the <a href="http://www.apache.org/">Apache Software Foundation</a>.<br/>
# MAGIC <br/>
# MAGIC <a href="https://databricks.com/privacy-policy">Privacy Policy</a> | <a href="https://databricks.com/terms-of-use">Terms of Use</a> | <a href="http://help.databricks.com/">Support</a>
