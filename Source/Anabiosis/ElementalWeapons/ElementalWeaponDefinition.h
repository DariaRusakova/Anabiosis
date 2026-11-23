#pragma once

#include "CoreMinimal.h"
#include "Engine/DataAsset.h"
#include "ElementalWeaponDefinition.generated.h"

class UStaticMesh;
class UAnimSequence;
class UMaterialInterface;

/** Weapon-local axes: X forward, Y right, Z up; all distances in centimetres. */
UCLASS(BlueprintType)
class ANABIOSIS_API UElementalWeaponDefinition : public UDataAsset
{
    GENERATED_BODY()
public:
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Weapon") TObjectPtr<UStaticMesh> Mesh;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Animation") TObjectPtr<UAnimSequence> HoldPose;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Animation") TObjectPtr<UAnimSequence> AttackPose;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Import") FVector MeshTranslation = FVector::ZeroVector;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Import") FRotator MeshRotation = FRotator::ZeroRotator;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Import") float MeshScale = 1;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Pose") FVector HipLocation = FVector(25,15,-18);
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Pose") FVector AimLocation = FVector(28,0,-10);
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Pose") FRotator HipRotation = FRotator(-3,-3,0);
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Pose") FRotator AimRotation = FRotator::ZeroRotator;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Grip") FVector RightHandOffset = FVector(-4,0,-2);
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Grip") FVector LeftHandOffset = FVector(5,-3.5,0);
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Grip") FVector RightElbowOffset = FVector(3,38,-38);
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Grip") FVector LeftElbowOffset = FVector(13,-40,-36);
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Attack") FVector MuzzleOffset = FVector(28,0,9);
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Attack") TObjectPtr<UMaterialInterface> StreamMaterial;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Attack", meta=(ClampMin="1")) float StreamRange = 520;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Attack", meta=(ClampMin="0.1")) float StreamWidth = 2;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Pose", meta=(ClampMin="0")) float RecoilScale = 1;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Pose", meta=(ClampMin="0")) float SwayScale = 1;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Pose", meta=(ClampMin="30",ClampMax="90")) float AimFOV = 55;
};
