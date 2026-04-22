import time

class PID:
    def __init__(self, Kp, Ki, Kd):
        self.Kp = Kp
        self.Ki = Ki
        self.Kd = Kd
        self.integral = 0
        self.prev_error = 0

    def hesapla(self, hedef, mevcut, dt):
        hata = hedef - mevcut
        self.integral += hata * dt
        turev = (hata - self.prev_error) / dt
        self.prev_error = hata
        cikti = self.Kp*hata + self.Ki*self.integral + self.Kd*turev
        return cikti

# Simülasyon
pid = PID(Kp=1.2, Ki=0.01, Kd=0.5)
hedef = 2.0      # 2 metre derinlik
derinlik = 0.0   # başlangıç
dt = 0.1         # 100ms

print("Hedef derinlik: 2.0 metre")
print("-" * 40)

for i in range(50):
    motor = pid.hesapla(hedef, derinlik, dt)
    derinlik += motor * dt * 0.3  # basit fizik
    print(f"Adım {i+1:2d} | Derinlik: {derinlik:.3f}m | Motor: {motor:.3f}")
    time.sleep(0.1)
