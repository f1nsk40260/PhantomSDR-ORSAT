// Stations CW régulières proposées dans la fenêtre du décodeur CW.
// Fréquences en kHz. Horaires en heure de Paris (Europe/Paris) : le passage
// heure d'été / heure d'hiver est géré automatiquement par CwSchedulePanel.
// days : 0 = dimanche, 1 = lundi … 6 = samedi.
// slots : [début, fin] en "HH:MM" ; fin = null → durée par défaut (60 min).
//
// Ajouter une station : une entrée de plus dans ce tableau, rien d'autre.

export const CW_DEFAULT_DURATION_MIN = 60;

export const CW_STATIONS = [
  {
    name: "FAV22",
    info: "Marine nationale — émission CW",
    freqs: [3881, 6825],
    schedule: [
      { days: [1, 2, 3, 4, 5], slots: [["10:30", "11:00"], ["13:30", "14:00"]] },
      { days: [6, 0], slots: [["09:00", "09:30"], ["10:20", "10:55"]] },
    ],
  },
  {
    name: "F9TM",
    info: "Émission CW du jeudi soir",
    freqs: [3536],
    schedule: [
      { days: [4], slots: [["19:15", null]] },
    ],
  },
];
