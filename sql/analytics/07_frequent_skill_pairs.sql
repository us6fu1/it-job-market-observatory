SELECT
    left_skill.skill_name AS skill_1,
    right_skill.skill_name AS skill_2,
    count(DISTINCT current.vacancy_sk) AS vacancy_count
FROM mart.v_current_vacancies AS current
JOIN dwh.bridge_vacancy_skill AS left_bridge
  ON left_bridge.vacancy_sk = current.vacancy_sk
JOIN dwh.bridge_vacancy_skill AS right_bridge
  ON right_bridge.vacancy_sk = current.vacancy_sk
 AND left_bridge.skill_sk < right_bridge.skill_sk
JOIN dwh.dim_skill AS left_skill ON left_skill.skill_sk = left_bridge.skill_sk
JOIN dwh.dim_skill AS right_skill ON right_skill.skill_sk = right_bridge.skill_sk
GROUP BY left_skill.skill_name, right_skill.skill_name
HAVING count(DISTINCT current.vacancy_sk) >= 2
ORDER BY vacancy_count DESC, skill_1, skill_2;
