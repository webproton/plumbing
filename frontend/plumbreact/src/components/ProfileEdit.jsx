import React, { useEffect, useState } from "react";
import ProfileService from "../services/ProfileService";
import PasswordChangeForm from "./PasswordChangeForm";
import EmailChangeForm from "./EmailChangeForm";


const ProfileEdit = ({ initialProfile, onCancel, onSave }) => {
  const [profile, setProfile] = useState(initialProfile);
  const [message, setMessage] = useState("");

  useEffect(() => {
    setProfile(initialProfile);
  }, [initialProfile]);

  const handleChange = (e) => {
    setProfile({ ...profile, [e.target.name]: e.target.value });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      const updated = await ProfileService.updateProfile(profile);
      setMessage("Профиль обновлён");
      onSave(updated);
    } catch (err) {
      setMessage("Ошибка обновления");
    }
  };

  if (!profile) return <div>Загрузка...</div>;

  return (
      <>



     <form id="profile-form" className="profile-form" onSubmit={handleSubmit}>


 
  
      <h2>Редактирование профиля</h2>
      

      <label>Имя</label>
      <input name="first_name" value={profile.first_name || ""} onChange={handleChange} />

      <label>Фамилия</label>
      <input name="last_name" value={profile.last_name || ""} onChange={handleChange} />

      <label>Отчество</label>
      <input name="middle_name" value={profile.middle_name || ""} onChange={handleChange} />

      <label>Город</label>
      <input name="city" value={profile.city || ""} onChange={handleChange} />

      <label>Адрес</label>
      <input name="address" value={profile.address || ""} onChange={handleChange} />

      <label>Пол</label>
      <select name="gender" value={profile.gender || ""} onChange={handleChange}>
        <option value="">—</option>
        <option value="male">Мужской</option>
        <option value="female">Женский</option>
      </select>

      <label>Дата рождения</label>
      <input type="date" name="birth_date" value={profile.birth_date || ""} onChange={handleChange} />


      <button type="submit" form="profile-form">💾 Сохранить</button>
      <button type="button" onClick={onCancel}>❌ Отмена</button>

      <hr />

        <div className="subform-container">
        <EmailChangeForm />
        <PasswordChangeForm />
      </div>



      {message && <p>{message}</p>}
    </form>

    </>
  );
};

export default ProfileEdit;
