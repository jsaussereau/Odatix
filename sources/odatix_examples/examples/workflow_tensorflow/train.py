import json
import sys

try:
    import tensorflow as tf  # type: ignore
except Exception as e:
    print("TensorFlow is required for this example.")
    print("Install it with: pip install tensorflow")
    print(f"Import error: {e}")
    sys.exit(1)


EPOCHS = 5
BATCH_SIZE = 32
SAMPLES = 512
INPUT_DIM = 16
N_CLASSES = 3

def report_progress(progress):
    with open("progress.txt", "w") as f:
        f.write(f"Progress: {progress}%")

report_progress(5)

class ProgressCallback(tf.keras.callbacks.Callback):
    def on_epoch_end(self, epoch, logs=None):
        logs = logs or {}
        progress = int(((epoch + 1) / EPOCHS) * 90 + 5) 
        report_progress(progress)


# Synthetic classification dataset
x = tf.random.normal((SAMPLES, INPUT_DIM))
y = tf.random.uniform((SAMPLES,), minval=0, maxval=N_CLASSES, dtype=tf.int32)

x_train, y_train = x[:400], y[:400]
x_val, y_val = x[400:], y[400:]

model = tf.keras.Sequential(
    [
        tf.keras.layers.Input(shape=(INPUT_DIM,)),
        tf.keras.layers.Dense(32, activation="relu"),
        tf.keras.layers.Dense(16, activation="relu"),
        tf.keras.layers.Dense(N_CLASSES, activation="softmax"),
    ]
)

model.compile(
    optimizer=tf.keras.optimizers.Adam(learning_rate=1e-3),
    loss="sparse_categorical_crossentropy",
    metrics=["accuracy"],
)

history = model.fit(
    x_train,
    y_train,
    validation_data=(x_val, y_val),
    epochs=EPOCHS,
    batch_size=BATCH_SIZE,
    verbose=1,
    callbacks=[ProgressCallback()],
)

report_progress(95)

final_loss = float(history.history["loss"][-1])
final_accuracy = float(history.history["accuracy"][-1])
final_val_loss = float(history.history["val_loss"][-1])
final_val_accuracy = float(history.history["val_accuracy"][-1])
best_val_accuracy = float(max(history.history["val_accuracy"]))

results = {
    "epochs": EPOCHS,
    "final_loss": final_loss,
    "final_accuracy": final_accuracy,
    "final_val_loss": final_val_loss,
    "final_val_accuracy": final_val_accuracy,
    "best_val_accuracy": best_val_accuracy,
}

with open("workflow_results.json", "w") as f:
    json.dump(results, f, indent=2)

print("Training finished")
print(json.dumps(results, indent=2))

report_progress(100)