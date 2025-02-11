# Databricks notebook source
# MAGIC %md
# MAGIC # AutoML forecasting example
# MAGIC ## Requirements
# MAGIC Databricks Runtime for Machine Learning 10.0 or above.  
# MAGIC To save model predictions, Databricks Runtime for Machine Learning 10.5 or above.

# COMMAND ----------

# MAGIC %md
# MAGIC ## COVID-19 dataset
# MAGIC The dataset contains records for the number of cases of the COVID-19 virus by date in the US, with additional geographical information. The goal is to forecast how many cases of the virus will occur over the next 30 days in the US.

# COMMAND ----------

import pyspark.pandas as ps
df = ps.read_csv("/databricks-datasets/COVID/covid-19-data")
df["date"] = ps.to_datetime(df['date'], errors='coerce')
df["cases"] = df["cases"].astype(int)
display(df)

# COMMAND ----------

# MAGIC %md
# MAGIC ## AutoML training
# MAGIC The following command starts an AutoML run. You must provide the column that the model should predict in the `target_col` argument and the time column. 
# MAGIC When the run completes, you can follow the link to the best trial notebook to examine the training code.  
# MAGIC 
# MAGIC This example also specifies:
# MAGIC - `horizon=30` to specify that AutoML should forecast 30 days into the future. 
# MAGIC - `frequency="d"` to specify that a forecast should be provided for each day. 
# MAGIC - `primary_metric="mdape"` to specify the metric to optimize for during training.

# COMMAND ----------

import databricks.automl
import logging

# Disable informational messages from fbprophet
logging.getLogger("py4j").setLevel(logging.WARNING)

# Note: If you are running Databricks Runtime for Machine Learning 10.4 or below, use this line instead:
# summary = databricks.automl.forecast(df, target_col="cases", time_col="date", horizon=30, frequency="d",  primary_metric="mdape")

summary = databricks.automl.forecast(df, target_col="cases", time_col="date", horizon=30, frequency="d",  primary_metric="mdape", output_database="default")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Next steps
# MAGIC * Explore the notebooks and experiments linked above.
# MAGIC * If the metrics for the best trial notebook look good, you can continue with the next cell.
# MAGIC * If you want to improve on the model generated by the best trial:
# MAGIC   * Go to the notebook with the best trial and clone it.
# MAGIC   * Edit the notebook as necessary to improve the model.
# MAGIC   * When you are satisfied with the model, note the URI where the artifact for the trained model is logged. Assign this URI to the `model_uri` variable in the next cell.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Show the predicted results from the best model
# MAGIC **Note:** This section requires Databricks Runtime for Machine Learning 10.5 or above.

# COMMAND ----------

# MAGIC %md
# MAGIC ### Load predictions from the best model
# MAGIC In Databricks Runtime for Machine Learning 10.5 or above, if `output_database` is provided, AutoML saves the predictions from the best model.  

# COMMAND ----------

# Load the saved predictions.
forecast_pd = spark.table(summary.output_table_name)
display(forecast_pd)

# COMMAND ----------

# MAGIC %md ## Use the model for forecasting
# MAGIC You can use the commands in this section with Databricks Runtime for Machine Learning 10.0 or above.

# COMMAND ----------

# MAGIC %md ### Load the model with MLflow
# MAGIC MLFlow allows you to easily import models back into Python by using the AutoML `trial_id` .

# COMMAND ----------

import mlflow.pyfunc
from mlflow.tracking import MlflowClient

run_id = MlflowClient()
trial_id = summary.best_trial.mlflow_run_id

model_uri = "runs:/{run_id}/model".format(run_id=trial_id)
pyfunc_model = mlflow.pyfunc.load_model(model_uri)

# COMMAND ----------

# MAGIC %md ### Use the model to make forecasts
# MAGIC 
# MAGIC Call the `predict_timeseries` model method to generate forecasts.    
# MAGIC In Databricks Runtime for Machine Learning 10.5 or above, you can set `include_history=False` to get the predicted data only.

# COMMAND ----------

forecasts = pyfunc_model._model_impl.python_model.predict_timeseries()
display(forecasts)

# Option for Databricks Runtime for Machine Learning 10.5 or above
# forecasts = pyfunc_model._model_impl.python_model.predict_timeseries(include_history=False)

# COMMAND ----------

# MAGIC %md ### Plot the forecasted points
# MAGIC In the plot below, the thick black line shows the time series dataset, and the blue line is the forecast created by the model.

# COMMAND ----------

df_true = df.groupby("date").agg(y=("cases", "avg")).reset_index().to_pandas()

# COMMAND ----------

import matplotlib.pyplot as plt

fig = plt.figure(facecolor='w', figsize=(10, 6))
ax = fig.add_subplot(111)
forecasts = pyfunc_model._model_impl.python_model.predict_timeseries(include_history=True)
fcst_t = forecasts['ds'].dt.to_pydatetime()
ax.plot(df_true['date'].dt.to_pydatetime(), df_true['y'], 'k.', label='Observed data points')
ax.plot(fcst_t, forecasts['yhat'], ls='-', c='#0072B2', label='Forecasts')
ax.fill_between(fcst_t, forecasts['yhat_lower'], forecasts['yhat_upper'],
                color='#0072B2', alpha=0.2, label='Uncertainty interval')
ax.legend()
plt.show()
