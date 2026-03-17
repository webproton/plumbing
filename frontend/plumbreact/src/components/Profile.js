// export default Profile;
import React, { useEffect, useState } from "react";
import ProfileService from "../services/ProfileService";
import ProfileEdit from "./ProfileEdit"; // ✅ Импортируем

const Profile = ({ user }) => {
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [editMode, setEditMode] = useState(false); // 🔁 Переключатель

  const [formData, setFormData] = useState({
    first_name: "",
    last_name: "",
  });

  useEffect(() => {
    ProfileService.getProfile()
      .then((data) => {
        setProfile(data);
        setLoading(false);
      })
      .catch(() => {
        setLoading(false);
      });
  }, []);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleSave = async () => {
    try {
      await ProfileService.updateProfile(formData);
      setEditMode(false);
    } catch (error) {
      console.error("Ошибка обновления профиля:", error);
    }
  };

    if (loading) return <div>Загрузка профиля...</div>;
    if (!profile) return <div>Нет данных профиля</div>;

  return (
    <div>
      {editMode ? (
        <>
          <ProfileEdit
            initialProfile={profile}
            onCancel={() => setEditMode(false)} // 👈 Отмена
            onSave={(updatedProfile) => {
              setProfile(updatedProfile);
              setEditMode(false);
            }}
          />
        </>
      ) : (
        <>
          <h2>Профиль</h2>
          <p><strong>Имя:</strong> {profile.first_name}</p>
          <p><strong>Фамилия:</strong> {profile.last_name}</p>
          <p><strong>Отчество:</strong> {profile.midle_name}</p>
          <p><strong>Пол:</strong> {profile.gender}</p>
          <p><strong>Email:</strong> {profile.email}</p>
          <p><strong>Телефон:</strong> {profile.phone_number}</p>
          <p><strong>Адрес:</strong> {profile.address}</p>
          <p><strong>Город:</strong> {profile.city}</p>
          <p><strong>День рождения:</strong> {profile.birth_date}</p>
          <button onClick={() => setEditMode(true)}>✏️ Редактировать</button>
        </>
      )}
      </div>

    
  );
};

export default Profile;
