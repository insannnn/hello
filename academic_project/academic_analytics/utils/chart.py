import io
import base64
import numpy as np
import matplotlib.pyplot as plt
from sklearn.preprocessing import MinMaxScaler

def get_radar_chart(student_data, population_avg):
    labels = list(student_data.index)
    values_student = student_data.values
    values_population = population_avg[labels].values

    all_values = np.vstack([values_student, values_population])
    scaler = MinMaxScaler()
    all_scaled = scaler.fit_transform(all_values)

    student_scaled = all_scaled[0]
    population_scaled = all_scaled[1]

    angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist()
    student_scaled = np.concatenate((student_scaled, [student_scaled[0]]))
    population_scaled = np.concatenate((population_scaled, [population_scaled[0]]))
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(6, 6), subplot_kw=dict(polar=True))
    ax.plot(angles, student_scaled, color="blue", linewidth=2, label="Student")
    ax.fill(angles, student_scaled, color="blue", alpha=0.25)
    ax.plot(angles, population_scaled, color="orange", linewidth=2, label="Population Avg")
    ax.fill(angles, population_scaled, color="orange", alpha=0.25)

    ax.set_thetagrids(np.degrees(angles[:-1]), labels)
    ax.set_title("Student vs Population")
    ax.legend()

    buf = io.BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format='png')
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode('utf-8')
